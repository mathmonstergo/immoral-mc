package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionException;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class QuestRequestCoordinatorTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID NEXT_LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000002");
    private static final UUID OPERATION_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_OPERATION_ID = UUID.fromString("30000000-0000-0000-0000-000000000002");
    private static final Instant NOW = Instant.parse("2026-07-13T12:00:00Z");

    @Test
    void coalescesOneRefreshPerPlayerProviderAndCleansUpAfterSuccess() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestInteractionState> firstNetwork = new CompletableFuture<>();
        gateway.refreshes.add(firstNetwork);
        gateway.refreshes.add(CompletableFuture.completedFuture(state(2, 2, "active")));
        QuestRequestCoordinator coordinator = coordinator(gateway, Runnable::run, new MutableClock(NOW));

        CompletableFuture<QuestInteractionState> first =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        CompletableFuture<QuestInteractionState> duplicate =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");

        assertSame(first, duplicate);
        assertEquals(1, gateway.refreshCalls.get());
        firstNetwork.complete(state(1, 1, "available"));
        assertEquals("available", first.join().providers().getFirst().quests().getFirst().state());

        coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join();
        assertEquals(2, gateway.refreshCalls.get());
    }

    @Test
    void publishesCacheEffectsOnlyThroughMainThreadDispatcher() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestInteractionState> network = new CompletableFuture<>();
        gateway.refreshes.add(network);
        Queue<Runnable> mainThread = new ArrayDeque<>();
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                mainThread::add,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletableFuture<QuestInteractionState> result =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        network.complete(state(1, 1, "available"));

        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
        assertFalse(result.isDone());
        mainThread.remove().run();
        assertEquals("available", cache.findLastConfirmed(PLAYER_ID, "old-man")
                .orElseThrow()
                .state()
                .providers()
                .getFirst()
                .quests()
                .getFirst()
                .state());
        assertTrue(result.isDone());
    }

    @Test
    void failureKeepsLastConfirmedCosmeticAndAppliesBoundedBackoff() {
        FakeGateway gateway = new FakeGateway();
        gateway.refreshes.add(CompletableFuture.failedFuture(new IOExceptionLikeFailure()));
        gateway.refreshes.add(CompletableFuture.failedFuture(new IOExceptionLikeFailure()));
        gateway.refreshes.add(CompletableFuture.failedFuture(new IOExceptionLikeFailure()));
        gateway.refreshes.add(CompletableFuture.completedFuture(state(4, 4, "ready_to_turn_in")));
        MutableClock clock = new MutableClock(NOW);
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionState confirmed = state(1, 1, "active");
        cache.publish(PLAYER_ID, "old-man", generation, confirmed, NOW);
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway, cache, Runnable::run, clock, Duration.ofMillis(100), Duration.ofMillis(250));

        assertThrows(
                CompletionException.class,
                () -> coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join());
        assertThrows(
                CompletionException.class,
                () -> coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join());
        assertEquals(1, gateway.refreshCalls.get());
        assertEquals(confirmed, cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state());

        clock.advance(Duration.ofMillis(100));
        assertThrows(
                CompletionException.class,
                () -> coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join());
        clock.advance(Duration.ofMillis(200));
        assertThrows(
                CompletionException.class,
                () -> coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join());
        clock.advance(Duration.ofMillis(249));
        assertThrows(
                CompletionException.class,
                () -> coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join());
        assertEquals(3, gateway.refreshCalls.get());

        clock.advance(Duration.ofMillis(1));
        coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man").join();
        assertEquals(4, gateway.refreshCalls.get());
    }

    @Test
    void successfulMutationInvalidatesOlderInspectAndWritesThroughReturnedSnapshot() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestInteractionState> inspectNetwork = new CompletableFuture<>();
        CompletableFuture<QuestMutationResult> mutationNetwork = new CompletableFuture<>();
        gateway.refreshes.add(inspectNetwork);
        gateway.accepts.add(mutationNetwork);
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletableFuture<QuestInteractionState> inspect =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        CompletableFuture<QuestMutationResult> accept = coordinator.accept(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID);
        QuestInteractionState acceptedState = state(1, 2, "active");
        mutationNetwork.complete(new QuestMutationResult(
                OPERATION_ID,
                true,
                acceptedState.providers().getFirst().quests().getFirst(),
                acceptedState));
        accept.join();

        assertTrue(inspectNetwork.isCancelled());
        assertThrows(java.util.concurrent.CancellationException.class, inspect::join);

        QuestInteractionState cached = cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state();
        assertEquals(2, cached.revision().quest());
        assertEquals("active", cached.providers().getFirst().quests().getFirst().state());
    }

    @Test
    void refreshDuringMutationReusesMutationProjectionWithoutAnotherHttpRequest() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestMutationResult> mutationNetwork = new CompletableFuture<>();
        gateway.accepts.add(mutationNetwork);
        QuestRequestCoordinator coordinator = coordinator(gateway, Runnable::run, new MutableClock(NOW));

        CompletableFuture<QuestMutationResult> accept = coordinator.accept(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID);
        CompletableFuture<QuestInteractionState> refresh =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        QuestInteractionState acceptedState = state(1, 2, "active");
        mutationNetwork.complete(new QuestMutationResult(
                OPERATION_ID,
                true,
                acceptedState.providers().getFirst().quests().getFirst(),
                acceptedState));

        assertEquals(acceptedState, accept.join().interactionState());
        assertEquals(acceptedState, refresh.join());
        assertEquals(0, gateway.refreshCalls.get());
        assertEquals(1, gateway.acceptCalls.get());
    }

    @Test
    void sameMutationCoalescesAndDifferentMutationFailsBusy() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestMutationResult> mutationNetwork = new CompletableFuture<>();
        gateway.accepts.add(mutationNetwork);
        QuestRequestCoordinator coordinator = coordinator(gateway, Runnable::run, new MutableClock(NOW));

        CompletableFuture<QuestMutationResult> first = coordinator.accept(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID);
        CompletableFuture<QuestMutationResult> duplicate = coordinator.accept(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID);
        CompletableFuture<QuestMutationResult> busy = coordinator.turnIn(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OTHER_OPERATION_ID);

        assertSame(first, duplicate);
        assertEquals(1, gateway.acceptCalls.get());
        CompletionException failure = assertThrows(CompletionException.class, busy::join);
        assertInstanceOf(QuestRequestCoordinator.QuestRequestBusyException.class, failure.getCause());
        assertEquals(0, gateway.turnInCalls.get());

        QuestInteractionState acceptedState = state(1, 2, "active");
        mutationNetwork.complete(new QuestMutationResult(
                OPERATION_ID,
                true,
                acceptedState.providers().getFirst().quests().getFirst(),
                acceptedState));
        first.join();
    }

    @Test
    void failedMutationNeverTurnsLastConfirmedCosmeticIntoAuthorization() {
        FakeGateway gateway = new FakeGateway();
        gateway.accepts.add(CompletableFuture.failedFuture(new IOExceptionLikeFailure()));
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionState confirmed = state(1, 1, "available");
        cache.publish(PLAYER_ID, "old-man", generation, confirmed, NOW);
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        assertThrows(
                CompletionException.class,
                () -> coordinator.accept(
                                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID)
                        .join());

        assertEquals(confirmed, cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state());
    }

    @Test
    void successfulTurnInWritesThroughCompletedProjection() {
        FakeGateway gateway = new FakeGateway();
        QuestInteractionState completedState = state(2, 3, "completed");
        gateway.turnIns.add(CompletableFuture.completedFuture(new QuestMutationResult(
                OPERATION_ID,
                true,
                completedState.providers().getFirst().quests().getFirst(),
                completedState)));
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        coordinator.turnIn(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID).join();

        assertEquals("completed", cache.findLastConfirmed(PLAYER_ID, "old-man")
                .orElseThrow()
                .state()
                .providers()
                .getFirst()
                .quests()
                .getFirst()
                .state());
    }

    @Test
    void mutationWithWrongLifeProjectionFailsInsteadOfPublishingSuccess() {
        FakeGateway gateway = new FakeGateway();
        QuestInteractionState wrongLife = state(1, 1, "active", NEXT_LIFE_ID);
        gateway.accepts.add(CompletableFuture.completedFuture(new QuestMutationResult(
                OPERATION_ID,
                true,
                wrongLife.providers().getFirst().quests().getFirst(),
                wrongLife)));
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletionException failure = assertThrows(
                CompletionException.class,
                () -> coordinator.accept(
                                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID)
                        .join());

        assertInstanceOf(QuestRequestCoordinator.StaleQuestResponseException.class, failure.getCause());
        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
    }

    @Test
    void clearPlayerInvalidatesInFlightResponseAndRemovesCoordinatorState() {
        FakeGateway gateway = new FakeGateway();
        CompletableFuture<QuestInteractionState> network = new CompletableFuture<>();
        gateway.refreshes.add(network);
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletableFuture<QuestInteractionState> refresh =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        coordinator.clearPlayer(PLAYER_ID);
        network.complete(state(1, 1, "available"));
        assertThrows(java.util.concurrent.CancellationException.class, refresh::join);

        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
    }

    @Test
    void clearPlayerPreventsLateNonCancellableMutationFromCompletingSuccessfully() {
        FakeGateway gateway = new FakeGateway();
        NonCancellableFuture<QuestMutationResult> network = new NonCancellableFuture<>();
        gateway.accepts.add(network);
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletableFuture<QuestMutationResult> mutation = coordinator.accept(
                PLAYER_ID, ACCOUNT_ID, LIFE_ID, "first-steps", "old-man", OPERATION_ID);
        coordinator.clearPlayer(PLAYER_ID);
        QuestInteractionState acceptedState = state(1, 1, "active");
        network.complete(new QuestMutationResult(
                OPERATION_ID,
                true,
                acceptedState.providers().getFirst().quests().getFirst(),
                acceptedState));

        assertThrows(java.util.concurrent.CancellationException.class, mutation::join);
        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
    }

    @Test
    void lifeSwitchInvalidatesOldRefreshWithoutRequiringExplicitClear() {
        FakeGateway gateway = new FakeGateway();
        NonCancellableFuture<QuestInteractionState> oldLifeNetwork = new NonCancellableFuture<>();
        CompletableFuture<QuestInteractionState> newLifeNetwork = new CompletableFuture<>();
        gateway.refreshes.add(oldLifeNetwork);
        gateway.refreshes.add(newLifeNetwork);
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestRequestCoordinator coordinator = new QuestRequestCoordinator(
                gateway,
                cache,
                Runnable::run,
                new MutableClock(NOW),
                Duration.ofMillis(100),
                Duration.ofSeconds(1));

        CompletableFuture<QuestInteractionState> oldRefresh =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, LIFE_ID, "old-man");
        CompletableFuture<QuestInteractionState> newRefresh =
                coordinator.refresh(PLAYER_ID, ACCOUNT_ID, NEXT_LIFE_ID, "old-man");
        oldLifeNetwork.complete(state(9, 9, "completed"));
        assertThrows(java.util.concurrent.CancellationException.class, oldRefresh::join);
        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());

        QuestInteractionState newLifeState = state(1, 0, "available", NEXT_LIFE_ID);
        newLifeNetwork.complete(newLifeState);

        assertEquals(newLifeState, newRefresh.join());
        assertEquals(NEXT_LIFE_ID, cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state().lifeId());
        assertEquals(2, gateway.refreshCalls.get());
    }

    private static QuestRequestCoordinator coordinator(
            FakeGateway gateway, QuestRequestCoordinator.MainThreadDispatcher dispatcher, Clock clock) {
        return new QuestRequestCoordinator(
                gateway,
                new QuestInteractionCache(),
                dispatcher,
                clock,
                Duration.ofMillis(100),
                Duration.ofSeconds(1));
    }

    private static QuestInteractionState state(long playerRevision, long questRevision, String questState) {
        return state(playerRevision, questRevision, questState, LIFE_ID);
    }

    private static QuestInteractionState state(
            long playerRevision, long questRevision, String questState, UUID lifeId) {
        ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                "first-steps", "初入凡尘", "main", questState, "remind", null, List.of());
        QuestProviderSnapshot provider = new QuestProviderSnapshot(
                "old-man", "first-steps:" + questState, List.of(quest), List.of("first-steps"), "first-steps", null);
        return new QuestInteractionState(
                1,
                ACCOUNT_ID,
                lifeId,
                new QuestRevisionVector(playerRevision, questRevision, "sha256:definitions"),
                List.of(provider),
                null,
                2000);
    }

    private static final class FakeGateway implements QuestRequestCoordinator.Gateway {
        private final AtomicInteger refreshCalls = new AtomicInteger();
        private final AtomicInteger acceptCalls = new AtomicInteger();
        private final AtomicInteger turnInCalls = new AtomicInteger();
        private final Queue<CompletableFuture<QuestInteractionState>> refreshes = new ArrayDeque<>();
        private final Queue<CompletableFuture<QuestMutationResult>> accepts = new ArrayDeque<>();
        private final Queue<CompletableFuture<QuestMutationResult>> turnIns = new ArrayDeque<>();

        @Override
        public CompletableFuture<QuestInteractionState> fetchQuestInteractionState(
                UUID accountId, List<String> providerIds) {
            refreshCalls.incrementAndGet();
            return refreshes.remove();
        }

        @Override
        public CompletableFuture<QuestMutationResult> acceptQuest(
                UUID accountId, String questId, String providerId, UUID operationId) {
            acceptCalls.incrementAndGet();
            return accepts.remove();
        }

        @Override
        public CompletableFuture<QuestMutationResult> turnInQuest(
                UUID accountId, String questId, String providerId, UUID operationId) {
            turnInCalls.incrementAndGet();
            return turnIns.remove();
        }
    }

    private static final class MutableClock extends Clock {
        private Instant instant;

        private MutableClock(Instant instant) {
            this.instant = instant;
        }

        void advance(Duration duration) {
            instant = instant.plus(duration);
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }

    private static final class IOExceptionLikeFailure extends RuntimeException {}

    private static final class NonCancellableFuture<T> extends CompletableFuture<T> {
        @Override
        public boolean cancel(boolean mayInterruptIfRunning) {
            return false;
        }
    }
}
