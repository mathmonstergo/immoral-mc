package com.immortalmc.adapter.outbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.immortalmc.adapter.client.CombatKillBatchResponse;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.CombatKillResult;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.combat.CombatAttributionKind;
import com.immortalmc.adapter.combat.CombatSource;
import com.immortalmc.adapter.mythicmobs.MythicMobDeathSnapshot;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class OutboxDeliveryWorkerTest {
    private static final Instant NOW = Instant.parse("2026-07-15T12:00:00Z");
    private static final UUID EVENT_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");

    @TempDir
    Path tempDir;

    @Test
    void policyAdaptsCadenceAndHonorsMaximumPendingAge() {
        OutboxDeliveryPolicy policy = policy();

        assertEquals(Duration.ofSeconds(1), policy.nextDelay(20.0, Duration.ZERO));
        assertEquals(100, policy.batchSize(20.0));
        assertEquals(Duration.ofSeconds(5), policy.nextDelay(16.0, Duration.ZERO));
        assertEquals(200, policy.batchSize(16.0));
        assertEquals(Duration.ZERO, policy.nextDelay(10.0, Duration.ofSeconds(30)));
        assertEquals(Duration.ofSeconds(4), policyWithHalfJitter().retryDelay(4));
    }

    @Test
    void terminalResultsAcknowledgeRowsExactlyOnce() throws Exception {
        try (SqliteKillOutbox outbox = outbox();
                OutboxDeliveryWorker worker = worker(
                        outbox,
                        requests -> CompletableFuture.completedFuture(response(requests)))) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);

            DeliveryRun run = worker.runOnce(20.0).get(2, TimeUnit.SECONDS);

            assertEquals(1, run.acknowledged());
            assertEquals(0, outbox.totalCount().get(2, TimeUnit.SECONDS));
        }
    }

    @Test
    void retryableFailureRetainsRowWithBackoffAndNonretryableFailureDeadLetters()
            throws Exception {
        try (SqliteKillOutbox retryOutbox = outbox(tempDir.resolve("retry.sqlite3"));
                OutboxDeliveryWorker retryWorker = worker(
                        retryOutbox,
                        requests -> CompletableFuture.failedFuture(
                                new GameServiceException(503, "service.not_ready", "Not ready", true)))) {
            retryOutbox.append(request()).get(2, TimeUnit.SECONDS);
            DeliveryRun run = retryWorker.runOnce(20.0).get(2, TimeUnit.SECONDS);
            assertEquals(1, run.retried());
            assertEquals(1, retryOutbox.pendingCount().get(2, TimeUnit.SECONDS));
            assertTrue(retryOutbox.claimDue(1, NOW, Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .isEmpty());
        }

        try (SqliteKillOutbox deadOutbox = outbox(tempDir.resolve("dead.sqlite3"));
                OutboxDeliveryWorker deadWorker = worker(
                        deadOutbox,
                        requests -> CompletableFuture.failedFuture(
                                new GameServiceException(400, "request.invalid", "Invalid", false)))) {
            deadOutbox.append(request()).get(2, TimeUnit.SECONDS);
            DeliveryRun run = deadWorker.runOnce(20.0).get(2, TimeUnit.SECONDS);
            assertEquals(1, run.deadLettered());
            assertEquals(1, deadOutbox.deadLetterCount().get(2, TimeUnit.SECONDS));
        }
    }

    @Test
    void permitsOnlyOneInFlightBatch() throws Exception {
        CompletableFuture<CombatKillBatchResponse> response = new CompletableFuture<>();
        CompletableFuture<Void> started = new CompletableFuture<>();
        AtomicInteger sends = new AtomicInteger();
        try (SqliteKillOutbox outbox = outbox();
                OutboxDeliveryWorker worker = worker(outbox, requests -> {
                    sends.incrementAndGet();
                    started.complete(null);
                    return response;
                })) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);
            CompletableFuture<DeliveryRun> first = worker.runOnce(20.0);
            started.get(2, TimeUnit.SECONDS);

            DeliveryRun skipped = worker.runOnce(20.0).get(2, TimeUnit.SECONDS);

            assertTrue(skipped.skipped());
            assertEquals(1, sends.get());
            response.complete(response(List.of(request())));
            assertFalse(first.get(2, TimeUnit.SECONDS).skipped());
        }
    }

    private OutboxDeliveryWorker worker(SqliteKillOutbox outbox, CombatBatchSender sender) {
        return new OutboxDeliveryWorker(
                outbox,
                sender,
                policy(),
                Clock.fixed(NOW, ZoneOffset.UTC),
                new RecordingAdapterLogger());
    }

    private static OutboxDeliveryPolicy policy() {
        return new OutboxDeliveryPolicy(
                Duration.ofSeconds(1),
                Duration.ofSeconds(5),
                17.0,
                100,
                200,
                Duration.ofSeconds(30),
                Duration.ofSeconds(30),
                20,
                Duration.ofSeconds(1),
                Duration.ofSeconds(60));
    }

    private static OutboxDeliveryPolicy policyWithHalfJitter() {
        return new OutboxDeliveryPolicy(
                Duration.ofSeconds(1),
                Duration.ofSeconds(5),
                17.0,
                100,
                200,
                Duration.ofSeconds(30),
                Duration.ofSeconds(30),
                20,
                Duration.ofSeconds(1),
                Duration.ofSeconds(60),
                () -> 0.5);
    }

    private SqliteKillOutbox outbox() {
        return outbox(tempDir.resolve("outbox.sqlite3"));
    }

    private static SqliteKillOutbox outbox(Path path) {
        return new SqliteKillOutbox(
                path,
                Duration.ofSeconds(5),
                64,
                Clock.fixed(NOW, ZoneOffset.UTC),
                new ObjectMapper());
    }

    private static CombatKillBatchResponse response(List<CombatKillEventRequest> requests) {
        return new CombatKillBatchResponse(
                1,
                requests.stream()
                        .map(request -> new CombatKillResult(
                                request.eventId(),
                                "not_rewardable",
                                UUID.fromString("66666666-6666-4666-8666-666666666666"),
                                null,
                                null,
                                null))
                        .toList())
                .validateAgainst(requests);
    }

    private static CombatKillEventRequest request() {
        UUID entityId = UUID.fromString("22222222-2222-4222-8222-222222222222");
        UUID playerId = UUID.fromString("33333333-3333-4333-8333-333333333333");
        UUID lifeId = UUID.fromString("44444444-4444-4444-8444-444444444444");
        return CombatKillEventRequest.fromSnapshot(new MythicMobDeathSnapshot(
                EVENT_ID,
                "main-1",
                entityId,
                "AzureWolf",
                new BigDecimal("12.5"),
                new CombatSource(
                        playerId,
                        lifeId,
                        "venom_mist",
                        UUID.fromString("55555555-5555-4555-8555-555555555555"),
                        CombatAttributionKind.DAMAGE_OVER_TIME,
                        NOW.minusSeconds(1),
                        NOW.plusSeconds(60)),
                "minecraft:overworld",
                12.5,
                64.0,
                -8.25,
                NOW));
    }
}
