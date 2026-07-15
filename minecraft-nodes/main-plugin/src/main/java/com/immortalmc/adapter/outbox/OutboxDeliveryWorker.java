package com.immortalmc.adapter.outbox;

import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.io.IOException;
import java.net.http.HttpTimeoutException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.DoubleSupplier;

public final class OutboxDeliveryWorker implements AutoCloseable {
    private final SqliteKillOutbox outbox;
    private final CombatBatchSender sender;
    private final OutboxDeliveryPolicy policy;
    private final Clock clock;
    private final AdapterLogger logger;
    private final ScheduledExecutorService scheduler;
    private final AtomicBoolean inFlight = new AtomicBoolean();
    private final AtomicBoolean closed = new AtomicBoolean();
    private volatile CompletableFuture<DeliveryRun> activeRun;
    private ScheduledFuture<?> scheduledRun;

    public OutboxDeliveryWorker(
            SqliteKillOutbox outbox,
            CombatBatchSender sender,
            OutboxDeliveryPolicy policy,
            Clock clock,
            AdapterLogger logger) {
        this.outbox = Objects.requireNonNull(outbox, "outbox");
        this.sender = Objects.requireNonNull(sender, "sender");
        this.policy = Objects.requireNonNull(policy, "policy");
        this.clock = Objects.requireNonNull(clock, "clock");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.scheduler = Executors.newSingleThreadScheduledExecutor(runnable -> {
            Thread thread = new Thread(runnable, "immortalmc-combat-outbox-delivery");
            thread.setDaemon(true);
            return thread;
        });
    }

    public CompletableFuture<DeliveryRun> runOnce(double tps) {
        if (!inFlight.compareAndSet(false, true)) {
            return CompletableFuture.completedFuture(DeliveryRun.skippedRun());
        }
        Instant now = clock.instant();
        CompletableFuture<DeliveryRun> result = outbox
                .claimDue(policy.batchSize(tps), now, policy.leaseDuration())
                .thenCompose(rows -> {
                    if (rows.isEmpty()) {
                        return CompletableFuture.completedFuture(new DeliveryRun(0, 0, 0, 0, false));
                    }
                    List<CombatKillEventRequest> requests = rows.stream()
                            .map(KillOutboxRow::request)
                            .toList();
                    return sender.send(requests)
                            .thenCompose(response -> acknowledge(rows))
                            .exceptionallyCompose(error -> handleFailure(rows, unwrap(error)));
                });
        activeRun = result;
        return result.whenComplete((ignored, error) -> {
            activeRun = null;
            inFlight.set(false);
        });
    }

    public synchronized void start(DoubleSupplier tpsSupplier) {
        Objects.requireNonNull(tpsSupplier, "tpsSupplier");
        if (closed.get() || scheduledRun != null) {
            throw new IllegalStateException("Outbox delivery worker is already started or closed");
        }
        scheduleNext(tpsSupplier, Duration.ZERO);
    }

    @Override
    public synchronized void close() {
        if (!closed.compareAndSet(false, true)) {
            return;
        }
        if (scheduledRun != null) {
            scheduledRun.cancel(false);
        }
        CompletableFuture<DeliveryRun> running = activeRun;
        if (running != null) {
            try {
                running.get(5, TimeUnit.SECONDS);
            } catch (Exception error) {
                logger.error("combat_outbox_delivery_shutdown_failed", error);
            }
        }
        scheduler.shutdownNow();
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                throw new IllegalStateException("Outbox delivery scheduler did not stop");
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while stopping outbox delivery", error);
        }
    }

    private CompletableFuture<DeliveryRun> acknowledge(List<KillOutboxRow> rows) {
        return outbox.acknowledge(rows.stream().map(row -> row.request().eventId()).toList())
                .thenApply(ignored -> new DeliveryRun(rows.size(), rows.size(), 0, 0, false));
    }

    private CompletableFuture<DeliveryRun> handleFailure(List<KillOutboxRow> rows, Throwable error) {
        boolean retryable = retryable(error);
        List<CompletableFuture<Void>> transitions = rows.stream()
                .map(row -> transitionFailure(row, error, retryable))
                .toList();
        return CompletableFuture.allOf(transitions.toArray(CompletableFuture[]::new))
                .thenApply(ignored -> retryable
                        ? new DeliveryRun(rows.size(), 0, (int) rows.stream()
                                .filter(row -> row.attemptCount() < policy.maxAttempts())
                                .count(), (int) rows.stream()
                                .filter(row -> row.attemptCount() >= policy.maxAttempts())
                                .count(), false)
                        : new DeliveryRun(rows.size(), 0, 0, rows.size(), false));
    }

    private CompletableFuture<Void> transitionFailure(
            KillOutboxRow row,
            Throwable error,
            boolean retryable) {
        if (retryable && row.attemptCount() < policy.maxAttempts()) {
            return outbox.retry(
                    row.request().eventId(),
                    clock.instant().plus(policy.retryDelay(row.attemptCount())),
                    message(error));
        }
        return outbox.deadLetter(row.request().eventId(), message(error));
    }

    private void scheduleNext(DoubleSupplier tpsSupplier, Duration delay) {
        scheduledRun = scheduler.schedule(() -> {
            double tps = tpsSupplier.getAsDouble();
            runOnce(tps).whenComplete((ignored, error) -> {
                if (error != null) {
                    logger.error("combat_outbox_delivery_failed", unwrap(error));
                }
                if (!closed.get()) {
                    outbox.oldestPendingAge(clock.instant()).whenComplete((age, ageError) -> {
                        Duration next = ageError == null
                                ? policy.nextDelay(tps, age.orElse(Duration.ZERO))
                                : policy.nextDelay(tps, Duration.ZERO);
                        scheduleNext(tpsSupplier, next);
                    });
                }
            });
        }, delay.toMillis(), TimeUnit.MILLISECONDS);
    }

    private static boolean retryable(Throwable error) {
        if (error instanceof GameServiceException exception) {
            return exception.retryable();
        }
        return error instanceof IOException || error instanceof HttpTimeoutException;
    }

    private static String message(Throwable error) {
        return error.getMessage() == null ? error.getClass().getSimpleName() : error.getMessage();
    }

    private static Throwable unwrap(Throwable error) {
        Throwable current = error;
        while ((current instanceof CompletionException) && current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }
}
