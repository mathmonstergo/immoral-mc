package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.List;
import java.util.Queue;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class QuestNpcCoordinatorTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000002");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000002");
    private static final UUID WORLD_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final Instant NOW = Instant.parse("2026-07-13T12:00:00Z");

    @Test
    void outsideToInsideUsesFreshCacheWithoutHttpAndDoesNotSpamWhileInside() {
        QuestInteractionCache cache = cached("available", "first-steps:available", "最近太不太平了...");
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(20, 0, 20)), NOW);
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusMillis(500));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusSeconds(1));

        assertEquals(List.of("§6老村民§7: §f最近太不太平了..."), barks);
        assertEquals(0, refresher.calls.get());
    }

    @Test
    void differentResolvedRuleKeyBypassesOldCooldown() {
        QuestInteractionCache cache = new QuestInteractionCache(Duration.ofMinutes(5));
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        publish(cache, "available", "old-man:first-steps-available", "最近太不太平了...");
        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusSeconds(1));
        publish(cache, "active", "old-man:first-steps-active", "去找鉴灵师看看吧。");
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusMillis(1500));

        assertEquals(
                List.of(
                        "§6老村民§7: §f最近太不太平了...",
                        "§6老村民§7: §f去找鉴灵师看看吧。"),
                barks);
        assertEquals(0, refresher.calls.get());
    }

    @Test
    void sameResolvedRuleKeyHonorsCooldownAcrossReentry() {
        QuestInteractionCache cache = new QuestInteractionCache(Duration.ofMinutes(5));
        publish(cache, "available", "old-man:first-steps-available", "最近太不太平了...");
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, new RecordingRefresher(), barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusSeconds(1));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusSeconds(2));
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusSeconds(60));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusSeconds(61));

        assertEquals(
                List.of(
                        "§6老村民§7: §f最近太不太平了...",
                        "§6老村民§7: §f最近太不太平了..."),
                barks);
    }

    @Test
    void refreshCompletionSpeaksImmediatelyWhenPlayerIsStillInside() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        refresher.response = CompletableFuture.completedFuture(
                state("available", "first-steps:available", "最近太不太平了..."));
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertEquals(List.of("§6老村民§7: §f最近太不太平了..."), barks);
    }

    @Test
    void mismatchedAccountInFreshCacheRefreshesBeforeSpeaking() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation =
                cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        assertTrue(cache.publish(
                PLAYER_ID,
                "old-man",
                generation,
                state(OTHER_ACCOUNT_ID, LIFE_ID, "available", "old-man:stale", "旧账号的话"),
                NOW));
        RecordingRefresher refresher = new RecordingRefresher();
        refresher.response = CompletableFuture.completedFuture(
                state("available", "old-man:fresh", "当前账号的话"));
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertEquals(1, refresher.calls.get());
        assertEquals(List.of("§6老村民§7: §f当前账号的话"), barks);
    }

    @Test
    void mismatchedLifeInFreshCacheRefreshesBeforeSpeaking() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation =
                cache.nextGeneration(PLAYER_ID, "old-man", OTHER_LIFE_ID);
        assertTrue(cache.publish(
                PLAYER_ID,
                "old-man",
                generation,
                state(ACCOUNT_ID, OTHER_LIFE_ID, "available", "old-man:stale", "旧人生的话"),
                NOW));
        RecordingRefresher refresher = new RecordingRefresher();
        refresher.response = CompletableFuture.completedFuture(
                state("available", "old-man:fresh", "当前人生的话"));
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertEquals(1, refresher.calls.get());
        assertEquals(List.of("§6老村民§7: §f当前人生的话"), barks);
    }

    @Test
    void refreshCompletionWithMismatchedAccountIsDropped() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        refresher.response = CompletableFuture.completedFuture(
                state(OTHER_ACCOUNT_ID, LIFE_ID, "available", "old-man:wrong", "错误账号的话"));
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertTrue(barks.isEmpty());
    }

    @Test
    void refreshCompletionWithMismatchedLifeIsDropped() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        refresher.response = CompletableFuture.completedFuture(
                state(ACCOUNT_ID, OTHER_LIFE_ID, "available", "old-man:wrong", "错误人生的话"));
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertTrue(barks.isEmpty());
    }

    @Test
    void refreshCompletionIsDroppedAfterPlayerLeavesRange() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusMillis(500));
        refresher.response.complete(
                state("available", "old-man:first-steps-available", "最近太不太平了..."));

        assertTrue(barks.isEmpty());
    }

    @Test
    void refreshCompletionFromPriorEntryIsDroppedAfterLeaveAndReentry() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        CompletableFuture<QuestInteractionState> first = new CompletableFuture<>();
        CompletableFuture<QuestInteractionState> second = new CompletableFuture<>();
        refresher.responses.add(first);
        refresher.responses.add(second);
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusMillis(1));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusMillis(2));

        first.complete(state("available", "old-man:old", "旧进入的话"));
        assertTrue(barks.isEmpty());

        second.complete(state("available", "old-man:new", "重新进入的话"));
        assertEquals(List.of("§6老村民§7: §f重新进入的话"), barks);
    }

    @Test
    void asyncCooldownStartsWhenBarkIsDelivered() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        CompletableFuture<QuestInteractionState> first = new CompletableFuture<>();
        refresher.responses.add(first);
        List<String> barks = new ArrayList<>();
        MutableClock clock = new MutableClock(NOW);
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100, clock);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        clock.advance(Duration.ofSeconds(30));
        first.complete(state("available", "old-man:cooldown", "第一次延迟话语"));

        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusSeconds(31));
        clock.advance(Duration.ofSeconds(31));
        refresher.response = CompletableFuture.completedFuture(
                state("available", "old-man:cooldown", "第二次话语"));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusSeconds(61));

        assertEquals(2, refresher.calls.get());
        assertEquals(List.of("§6老村民§7: §f第一次延迟话语"), barks);
    }

    @Test
    void resolvedProviderWithoutBarkStaysSilentWithoutRefreshing() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation =
                cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        cache.publish(
                PLAYER_ID,
                "old-man",
                generation,
                state("available", "old-man:none", null),
                NOW);
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);

        assertTrue(barks.isEmpty());
        assertEquals(0, refresher.calls.get());
    }

    @Test
    void chunkIndexLimitsCandidateChecksAndCarriesPlayerWorkAcrossTicks() {
        QuestInteractionCache cache = cached("available", "first-steps:available", "bark");
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcChunkIndex index = new QuestNpcChunkIndex();
        List<QuestNpcPosition> npcs = new ArrayList<>();
        for (int indexValue = 0; indexValue < 25; indexValue++) {
            npcs.add(new QuestNpcPosition(
                    new UUID(0, 5000 + indexValue),
                    "old-man",
                    WORLD_ID,
                    indexValue % 5,
                    0,
                    indexValue / 5,
                    0,
                    0));
        }
        index.replaceAll(npcs);
        QuestNpcCoordinator coordinator = new QuestNpcCoordinator(
                index,
                cache,
                refresher,
                (playerId, text) -> barks.add(text),
                6.0,
                Duration.ofSeconds(60),
                10);
        List<QuestPlayerPosition> players = new ArrayList<>();
        for (int playerIndex = 0; playerIndex < 100; playerIndex++) {
            players.add(new QuestPlayerPosition(
                    new UUID(0, 1000 + playerIndex), ACCOUNT_ID, LIFE_ID, WORLD_ID, 1, 0, 1, 0, 0));
        }

        QuestNpcCoordinator.ScanStats first = coordinator.tick(players, NOW);
        QuestNpcCoordinator.ScanStats second = coordinator.tick(players, NOW.plusMillis(500));

        assertEquals(10, first.playersProcessed());
        assertEquals(10, second.playersProcessed());
        assertEquals(250, first.candidateChecks());
        assertEquals(250, second.candidateChecks());
    }

    private static QuestNpcCoordinator coordinator(
            QuestInteractionCache cache,
            RecordingRefresher refresher,
            List<String> barks,
            int maxPlayers) {
        return coordinator(cache, refresher, barks, maxPlayers, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private static QuestNpcCoordinator coordinator(
            QuestInteractionCache cache,
            RecordingRefresher refresher,
            List<String> barks,
            int maxPlayers,
            Clock clock) {
        QuestNpcChunkIndex index = new QuestNpcChunkIndex();
        index.replaceAll(List.of(new QuestNpcPosition(NPC_ID, "old-man", WORLD_ID, 0, 0, 0, 0, 0)));
        return new QuestNpcCoordinator(
                index,
                cache,
                refresher,
                (playerId, text) -> barks.add(text),
                6.0,
                Duration.ofSeconds(60),
                maxPlayers,
                clock);
    }

    private static QuestPlayerPosition player(double x, double y, double z) {
        return new QuestPlayerPosition(PLAYER_ID, ACCOUNT_ID, LIFE_ID, WORLD_ID, x, y, z, ((int) x) >> 4, ((int) z) >> 4);
    }

    private static QuestInteractionCache cached(String state, String key, String text) {
        QuestInteractionCache cache = new QuestInteractionCache();
        publish(cache, state, key, text);
        return cache;
    }

    private static void publish(QuestInteractionCache cache, String state, String key, String text) {
        QuestInteractionCache.Generation generation = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        cache.publish(PLAYER_ID, "old-man", generation, state(state, key, text), NOW);
    }

    private static QuestInteractionState state(String questState, String key, String text) {
        return state(ACCOUNT_ID, LIFE_ID, questState, key, text);
    }

    private static QuestInteractionState state(
            UUID accountId,
            UUID lifeId,
            String questState,
            String key,
            String text) {
        ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                "first-steps", "初入凡尘", "去村口看看。", "main", questState, "remind", null, List.of(), List.of());
        QuestProviderSnapshot.ProximityBarkSnapshot bark = text == null
                ? null
                : new QuestProviderSnapshot.ProximityBarkSnapshot(key, "老村民", text, 60);
        QuestProviderSnapshot provider = new QuestProviderSnapshot(
                "old-man", key, List.of(quest), List.of("first-steps"), "first-steps", bark);
        return new QuestInteractionState(
                2,
                accountId,
                lifeId,
                new QuestRevisionVector(1, 1, 0, "sha256:definitions"),
                List.of(provider),
                null,
                2000);
    }

    private static final class RecordingRefresher implements QuestNpcCoordinator.Refresher {
        private final AtomicInteger calls = new AtomicInteger();
        private final Queue<CompletableFuture<QuestInteractionState>> responses = new ArrayDeque<>();
        private CompletableFuture<QuestInteractionState> response = new CompletableFuture<>();

        @Override
        public CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId) {
            calls.incrementAndGet();
            return responses.isEmpty() ? response : responses.remove();
        }
    }

    private static final class MutableClock extends Clock {
        private Instant current;

        private MutableClock(Instant current) {
            this.current = current;
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
            return current;
        }

        private void advance(Duration duration) {
            current = current.plus(duration);
        }
    }

}
