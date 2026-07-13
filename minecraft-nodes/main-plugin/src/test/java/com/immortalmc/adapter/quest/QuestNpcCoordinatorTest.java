package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class QuestNpcCoordinatorTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
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
    void missingCacheSchedulesOneRefreshAndStateChangeBypassesOldCooldown() {
        QuestInteractionCache cache = new QuestInteractionCache();
        RecordingRefresher refresher = new RecordingRefresher();
        List<String> barks = new ArrayList<>();
        QuestNpcCoordinator coordinator = coordinator(cache, refresher, barks, 100);

        coordinator.tick(List.of(player(1, 0, 1)), NOW);
        assertEquals(1, refresher.calls.get());
        assertTrue(barks.isEmpty());

        publish(cache, "active", "first-steps:active", "去找鉴灵师看看吧。");
        coordinator.tick(List.of(player(20, 0, 20)), NOW.plusSeconds(1));
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusMillis(1500));

        assertEquals(List.of("§6老村民§7: §f去找鉴灵师看看吧。"), barks);
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
                new QuestOfferSessionStore(),
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

    @Test
    void sessionValidationCancelsRangeWorldTimeoutAndMissingPlayer() {
        QuestOfferSessionStore sessions = new QuestOfferSessionStore();
        RecordingLabel label = new RecordingLabel();
        QuestOfferSession session = sessions.start(
                PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 0, 0, 0, NOW, label);
        sessions.markAwaitingConfirmation(session.token(), NOW);
        QuestNpcCoordinator coordinator = coordinator(new QuestInteractionCache(), new RecordingRefresher(), new ArrayList<>(), 100, sessions);

        coordinator.tick(List.of(player(7, 0, 0)), NOW.plusSeconds(1));

        assertTrue(sessions.find(PLAYER_ID).isEmpty());
        assertEquals(1, label.removals.get());
    }

    @Test
    void sessionValidationCancelsWhenNpcDisappearsFromIndex() {
        QuestOfferSessionStore sessions = new QuestOfferSessionStore();
        RecordingLabel label = new RecordingLabel();
        sessions.start(PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 0, 0, 0, NOW, label);
        QuestNpcChunkIndex index = new QuestNpcChunkIndex();
        index.replaceAll(List.of(new QuestNpcPosition(NPC_ID, "old-man", WORLD_ID, 0, 0, 0, 0, 0)));
        QuestNpcCoordinator coordinator = new QuestNpcCoordinator(
                index,
                new QuestInteractionCache(),
                new RecordingRefresher(),
                (playerId, text) -> {},
                sessions,
                6.0,
                Duration.ofSeconds(60),
                100);

        index.replaceAll(List.of());
        coordinator.tick(List.of(player(1, 0, 1)), NOW.plusSeconds(1));

        assertTrue(sessions.find(PLAYER_ID).isEmpty());
        assertEquals(1, label.removals.get());
    }

    private static QuestNpcCoordinator coordinator(
            QuestInteractionCache cache,
            RecordingRefresher refresher,
            List<String> barks,
            int maxPlayers) {
        return coordinator(cache, refresher, barks, maxPlayers, new QuestOfferSessionStore());
    }

    private static QuestNpcCoordinator coordinator(
            QuestInteractionCache cache,
            RecordingRefresher refresher,
            List<String> barks,
            int maxPlayers,
            QuestOfferSessionStore sessions) {
        QuestNpcChunkIndex index = new QuestNpcChunkIndex();
        index.replaceAll(List.of(new QuestNpcPosition(NPC_ID, "old-man", WORLD_ID, 0, 0, 0, 0, 0)));
        return new QuestNpcCoordinator(
                index,
                cache,
                refresher,
                (playerId, text) -> barks.add(text),
                sessions,
                6.0,
                Duration.ofSeconds(60),
                maxPlayers);
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
        ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                "first-steps", "初入凡尘", "main", questState, "remind", null, List.of());
        QuestProviderSnapshot.ProximityBarkSnapshot bark =
                new QuestProviderSnapshot.ProximityBarkSnapshot(key, "老村民", text, 60);
        QuestProviderSnapshot provider = new QuestProviderSnapshot(
                "old-man", key, List.of(quest), List.of("first-steps"), "first-steps", bark);
        return new QuestInteractionState(
                1,
                ACCOUNT_ID,
                LIFE_ID,
                new QuestRevisionVector(1, 1, "sha256:definitions"),
                List.of(provider),
                null,
                2000);
    }

    private static final class RecordingRefresher implements QuestNpcCoordinator.Refresher {
        private final AtomicInteger calls = new AtomicInteger();
        private CompletableFuture<QuestInteractionState> response = new CompletableFuture<>();

        @Override
        public CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId) {
            calls.incrementAndGet();
            return response;
        }
    }

    private static final class RecordingLabel implements QuestOfferLabel {
        private final AtomicInteger removals = new AtomicInteger();

        @Override
        public void showAwaitingConfirmation() {}

        @Override
        public void remove() {
            removals.incrementAndGet();
        }
    }
}
