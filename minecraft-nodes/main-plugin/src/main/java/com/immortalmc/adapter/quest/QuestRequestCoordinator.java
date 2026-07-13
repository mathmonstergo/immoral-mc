package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.ExecutionException;

public final class QuestRequestCoordinator implements QuestInteractionService {
    private static final Duration DEFAULT_BACKOFF_BASE = Duration.ofMillis(250);
    private static final Duration DEFAULT_BACKOFF_MAX = Duration.ofSeconds(2);

    private final Object lock = new Object();
    private final Gateway gateway;
    private final QuestInteractionCache cache;
    private final MainThreadDispatcher mainThreadDispatcher;
    private final Clock clock;
    private final Duration backoffBase;
    private final Duration backoffMax;
    private final Map<Key, PendingRequest> inFlightRequests = new HashMap<>();
    private final Map<Key, FailureState> refreshFailures = new HashMap<>();

    public QuestRequestCoordinator(
            GameServiceClient client,
            QuestInteractionCache cache,
            MainThreadDispatcher mainThreadDispatcher) {
        this(
                new GameServiceGateway(client),
                cache,
                mainThreadDispatcher,
                Clock.systemUTC(),
                DEFAULT_BACKOFF_BASE,
                DEFAULT_BACKOFF_MAX);
    }

    QuestRequestCoordinator(
            Gateway gateway,
            QuestInteractionCache cache,
            MainThreadDispatcher mainThreadDispatcher,
            Clock clock,
            Duration backoffBase,
            Duration backoffMax) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
        this.cache = Objects.requireNonNull(cache, "cache");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
        this.clock = Objects.requireNonNull(clock, "clock");
        this.backoffBase = requirePositive(backoffBase, "backoffBase");
        this.backoffMax = requirePositive(backoffMax, "backoffMax");
        if (backoffMax.compareTo(backoffBase) < 0) {
            throw new IllegalArgumentException("backoffMax must not be shorter than backoffBase");
        }
    }

    @Override
    public CompletableFuture<QuestInteractionState> refresh(
            UUID playerId, UUID accountId, UUID expectedLifeId, String providerId) {
        Key key = new Key(playerId, providerId);
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(expectedLifeId, "expectedLifeId");
        synchronized (lock) {
            PendingRequest existing = inFlightRequests.get(key);
            if (existing != null && !existing.expectedLifeId.equals(expectedLifeId)) {
                invalidateLocked(key, existing);
                existing = null;
            }
            if (existing != null) {
                if (existing.kind == RequestKind.REFRESH) {
                    return refreshPublished(existing);
                }
                return mutationPublished(existing).thenApply(QuestMutationResult::interactionState);
            }

            FailureState failure = refreshFailures.get(key);
            if (failure != null && !failure.expectedLifeId().equals(expectedLifeId)) {
                refreshFailures.remove(key);
                failure = null;
            }
            if (failure != null && clock.instant().isBefore(failure.retryAt())) {
                return CompletableFuture.failedFuture(failure.error());
            }

            QuestInteractionCache.Generation generation =
                    cache.nextGeneration(playerId, providerId, expectedLifeId);
            CompletableFuture<QuestInteractionState> published = new CompletableFuture<>();
            PendingRequest pending = PendingRequest.refresh(expectedLifeId, generation, published);
            inFlightRequests.put(key, pending);
            CompletableFuture<QuestInteractionState> network = callRefresh(accountId, providerId);
            pending.network = network;
            network.whenComplete((state, error) -> dispatchRefreshCompletion(key, pending, state, error));
            return published;
        }
    }

    @Override
    public CompletableFuture<QuestMutationResult> accept(
            UUID playerId,
            UUID accountId,
            UUID expectedLifeId,
            String questId,
            String providerId,
            UUID operationId) {
        MutationIdentity identity = new MutationIdentity(
                MutationCommand.ACCEPT, accountId, expectedLifeId, questId, providerId, operationId);
        return mutate(playerId, identity, () -> gateway.acceptQuest(accountId, questId, providerId, operationId));
    }

    @Override
    public CompletableFuture<QuestMutationResult> turnIn(
            UUID playerId,
            UUID accountId,
            UUID expectedLifeId,
            String questId,
            String providerId,
            UUID operationId) {
        MutationIdentity identity = new MutationIdentity(
                MutationCommand.TURN_IN, accountId, expectedLifeId, questId, providerId, operationId);
        return mutate(playerId, identity, () -> gateway.turnInQuest(accountId, questId, providerId, operationId));
    }

    public void clearPlayer(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        synchronized (lock) {
            List<Map.Entry<Key, PendingRequest>> matches = inFlightRequests.entrySet().stream()
                    .filter(entry -> entry.getKey().playerId().equals(playerId))
                    .toList();
            matches.forEach(entry -> invalidateLocked(entry.getKey(), entry.getValue()));
            refreshFailures.keySet().removeIf(key -> key.playerId().equals(playerId));
        }
        cache.clearPlayer(playerId);
    }

    public void clear() {
        synchronized (lock) {
            List<Map.Entry<Key, PendingRequest>> pending = List.copyOf(inFlightRequests.entrySet());
            pending.forEach(entry -> invalidateLocked(entry.getKey(), entry.getValue()));
            refreshFailures.clear();
        }
        cache.clear();
    }

    private CompletableFuture<QuestMutationResult> mutate(
            UUID playerId, MutationIdentity identity, FutureSupplier<QuestMutationResult> request) {
        Key key = new Key(playerId, identity.providerId());
        synchronized (lock) {
            PendingRequest existing = inFlightRequests.get(key);
            if (existing != null && !existing.expectedLifeId.equals(identity.expectedLifeId())) {
                invalidateLocked(key, existing);
                existing = null;
            }
            if (existing != null && existing.kind == RequestKind.MUTATION) {
                if (existing.mutationIdentity.equals(identity)) {
                    return mutationPublished(existing);
                }
                return CompletableFuture.failedFuture(new QuestRequestBusyException());
            }
            if (existing != null) {
                invalidateLocked(key, existing);
            }

            QuestInteractionCache.Generation generation =
                    cache.nextGeneration(playerId, identity.providerId(), identity.expectedLifeId());
            CompletableFuture<QuestMutationResult> published = new CompletableFuture<>();
            PendingRequest pending = PendingRequest.mutation(identity, generation, published);
            inFlightRequests.put(key, pending);
            CompletableFuture<QuestMutationResult> network = callMutation(request);
            pending.network = network;
            network.whenComplete((result, error) -> dispatchMutationCompletion(key, pending, result, error));
            return published;
        }
    }

    private CompletableFuture<QuestInteractionState> callRefresh(UUID accountId, String providerId) {
        try {
            return gateway.fetchQuestInteractionState(accountId, List.of(providerId));
        } catch (Throwable error) {
            return CompletableFuture.failedFuture(error);
        }
    }

    private static CompletableFuture<QuestMutationResult> callMutation(FutureSupplier<QuestMutationResult> request) {
        try {
            return request.get();
        } catch (Throwable error) {
            return CompletableFuture.failedFuture(error);
        }
    }

    private void dispatchRefreshCompletion(
            Key key, PendingRequest pending, QuestInteractionState state, Throwable error) {
        try {
            mainThreadDispatcher.dispatch(() -> finishRefresh(key, pending, state, error));
        } catch (Throwable dispatchError) {
            failDispatch(key, pending, dispatchError);
        }
    }

    private void dispatchMutationCompletion(
            Key key, PendingRequest pending, QuestMutationResult result, Throwable error) {
        try {
            mainThreadDispatcher.dispatch(() -> finishMutation(key, pending, result, error));
        } catch (Throwable dispatchError) {
            failDispatch(key, pending, dispatchError);
        }
    }

    private void finishRefresh(Key key, PendingRequest pending, QuestInteractionState state, Throwable error) {
        CompletableFuture<QuestInteractionState> published = refreshPublished(pending);
        synchronized (lock) {
            if (!isCurrentLocked(key, pending)) {
                return;
            }
            inFlightRequests.remove(key);
            if (error != null) {
                Throwable cause = unwrap(error);
                recordRefreshFailureLocked(key, pending.expectedLifeId, cause);
                published.completeExceptionally(cause);
                return;
            }

            boolean applied = cache.publish(
                    key.playerId(), key.providerId(), pending.generation, state, clock.instant());
            refreshFailures.remove(key);
            if (applied) {
                published.complete(state);
                return;
            }
            cache.findLastConfirmed(key.playerId(), key.providerId())
                    .ifPresentOrElse(
                            entry -> published.complete(entry.state()),
                            () -> published.completeExceptionally(new StaleQuestResponseException()));
        }
    }

    private void finishMutation(Key key, PendingRequest pending, QuestMutationResult result, Throwable error) {
        CompletableFuture<QuestMutationResult> published = mutationPublished(pending);
        synchronized (lock) {
            if (!isCurrentLocked(key, pending)) {
                return;
            }
            inFlightRequests.remove(key);
            if (error != null) {
                published.completeExceptionally(unwrap(error));
                return;
            }

            boolean applied = cache.publish(
                    key.playerId(),
                    key.providerId(),
                    pending.generation,
                    result.interactionState(),
                    clock.instant());
            if (!applied) {
                published.completeExceptionally(new StaleQuestResponseException());
                return;
            }
            refreshFailures.remove(key);
            published.complete(result);
        }
    }

    private void failDispatch(Key key, PendingRequest pending, Throwable error) {
        synchronized (lock) {
            if (!isCurrentLocked(key, pending)) {
                return;
            }
            inFlightRequests.remove(key);
            pending.published.completeExceptionally(error);
        }
    }

    private boolean isCurrentLocked(Key key, PendingRequest pending) {
        return !pending.invalidated && inFlightRequests.get(key) == pending;
    }

    private void invalidateLocked(Key key, PendingRequest pending) {
        if (inFlightRequests.get(key) == pending) {
            inFlightRequests.remove(key);
        }
        pending.invalidated = true;
        pending.published.cancel(false);
        if (pending.network != null) {
            pending.network.cancel(true);
        }
    }

    private void recordRefreshFailureLocked(Key key, UUID expectedLifeId, Throwable error) {
        FailureState current = refreshFailures.get(key);
        int attempts = current != null && current.expectedLifeId().equals(expectedLifeId)
                ? current.attempts() + 1
                : 1;
        refreshFailures.put(
                key,
                new FailureState(attempts, expectedLifeId, clock.instant().plus(backoffDelay(attempts)), error));
    }

    private Duration backoffDelay(int attempts) {
        Duration delay = backoffBase;
        for (int index = 1; index < attempts && delay.compareTo(backoffMax) < 0; index++) {
            if (delay.compareTo(backoffMax.dividedBy(2)) > 0) {
                return backoffMax;
            }
            delay = delay.multipliedBy(2);
        }
        return delay.compareTo(backoffMax) > 0 ? backoffMax : delay;
    }

    private static Throwable unwrap(Throwable error) {
        Throwable current = error;
        while ((current instanceof CompletionException || current instanceof ExecutionException)
                && current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }

    private static Duration requirePositive(Duration duration, String name) {
        Objects.requireNonNull(duration, name);
        if (duration.isNegative() || duration.isZero()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return duration;
    }

    @SuppressWarnings("unchecked")
    private static CompletableFuture<QuestInteractionState> refreshPublished(PendingRequest pending) {
        return (CompletableFuture<QuestInteractionState>) pending.published;
    }

    @SuppressWarnings("unchecked")
    private static CompletableFuture<QuestMutationResult> mutationPublished(PendingRequest pending) {
        return (CompletableFuture<QuestMutationResult>) pending.published;
    }

    public interface Gateway {
        CompletableFuture<QuestInteractionState> fetchQuestInteractionState(
                UUID accountId, List<String> providerIds);

        CompletableFuture<QuestMutationResult> acceptQuest(
                UUID accountId, String questId, String providerId, UUID operationId);

        CompletableFuture<QuestMutationResult> turnInQuest(
                UUID accountId, String questId, String providerId, UUID operationId);
    }

    @FunctionalInterface
    public interface MainThreadDispatcher {
        void dispatch(Runnable action);
    }

    public static final class QuestRequestBusyException extends RuntimeException {
        private QuestRequestBusyException() {
            super("Another quest mutation is already in progress for this provider");
        }
    }

    public static final class StaleQuestResponseException extends RuntimeException {
        private StaleQuestResponseException() {
            super("Quest response was superseded or did not match the expected life");
        }
    }

    @FunctionalInterface
    private interface FutureSupplier<T> {
        CompletableFuture<T> get();
    }

    private enum RequestKind {
        REFRESH,
        MUTATION
    }

    private enum MutationCommand {
        ACCEPT,
        TURN_IN
    }

    private static final class PendingRequest {
        private final RequestKind kind;
        private final UUID expectedLifeId;
        private final QuestInteractionCache.Generation generation;
        private final MutationIdentity mutationIdentity;
        private final CompletableFuture<?> published;
        private CompletableFuture<?> network;
        private boolean invalidated;

        private PendingRequest(
                RequestKind kind,
                UUID expectedLifeId,
                QuestInteractionCache.Generation generation,
                MutationIdentity mutationIdentity,
                CompletableFuture<?> published) {
            this.kind = kind;
            this.expectedLifeId = expectedLifeId;
            this.generation = generation;
            this.mutationIdentity = mutationIdentity;
            this.published = published;
        }

        private static PendingRequest refresh(
                UUID expectedLifeId,
                QuestInteractionCache.Generation generation,
                CompletableFuture<QuestInteractionState> published) {
            return new PendingRequest(RequestKind.REFRESH, expectedLifeId, generation, null, published);
        }

        private static PendingRequest mutation(
                MutationIdentity identity,
                QuestInteractionCache.Generation generation,
                CompletableFuture<QuestMutationResult> published) {
            return new PendingRequest(
                    RequestKind.MUTATION, identity.expectedLifeId(), generation, identity, published);
        }
    }

    private record Key(UUID playerId, String providerId) {
        private Key {
            Objects.requireNonNull(playerId, "playerId");
            Objects.requireNonNull(providerId, "providerId");
        }
    }

    private record MutationIdentity(
            MutationCommand command,
            UUID accountId,
            UUID expectedLifeId,
            String questId,
            String providerId,
            UUID operationId) {
        private MutationIdentity {
            Objects.requireNonNull(command, "command");
            Objects.requireNonNull(accountId, "accountId");
            Objects.requireNonNull(expectedLifeId, "expectedLifeId");
            Objects.requireNonNull(questId, "questId");
            Objects.requireNonNull(providerId, "providerId");
            Objects.requireNonNull(operationId, "operationId");
        }
    }

    private record FailureState(int attempts, UUID expectedLifeId, Instant retryAt, Throwable error) {}

    private static final class GameServiceGateway implements Gateway {
        private final GameServiceClient client;

        private GameServiceGateway(GameServiceClient client) {
            this.client = Objects.requireNonNull(client, "client");
        }

        @Override
        public CompletableFuture<QuestInteractionState> fetchQuestInteractionState(
                UUID accountId, List<String> providerIds) {
            return client.fetchQuestInteractionState(accountId, providerIds);
        }

        @Override
        public CompletableFuture<QuestMutationResult> acceptQuest(
                UUID accountId, String questId, String providerId, UUID operationId) {
            return client.acceptQuest(accountId, questId, providerId, operationId);
        }

        @Override
        public CompletableFuture<QuestMutationResult> turnInQuest(
                UUID accountId, String questId, String providerId, UUID operationId) {
            return client.turnInQuest(accountId, questId, providerId, operationId);
        }
    }
}
