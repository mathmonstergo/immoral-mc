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
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class QuestInteractionCacheTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID NEXT_LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000002");
    private static final Instant FETCHED_AT = Instant.parse("2026-07-13T12:00:00Z");

    @Test
    void presentationIsFreshForLessThanTwoSecondsAndStaleSnapshotRemainsReadable() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation generation = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionState state = state(2, 3, "active");
        assertTrue(cache.publish(PLAYER_ID, "old-man", generation, state, FETCHED_AT));

        assertTrue(cache.findFresh(PLAYER_ID, "old-man", FETCHED_AT.plusMillis(1999)).isPresent());
        assertTrue(cache.findFresh(PLAYER_ID, "old-man", FETCHED_AT.plusSeconds(2)).isEmpty());
        assertEquals(state, cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state());
    }

    @Test
    void rejectsOlderGenerationAndLowerAuthoritativeRevision() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation firstGeneration = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionState confirmed = state(4, 7, "ready_to_turn_in");
        assertTrue(cache.publish(PLAYER_ID, "old-man", firstGeneration, confirmed, FETCHED_AT));

        QuestInteractionCache.Generation newerGeneration = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        assertFalse(cache.publish(PLAYER_ID, "old-man", firstGeneration, state(5, 8, "completed"), FETCHED_AT));
        assertFalse(cache.publish(PLAYER_ID, "old-man", newerGeneration, state(4, 6, "active"), FETCHED_AT));

        assertEquals(confirmed, cache.findLastConfirmed(PLAYER_ID, "old-man").orElseThrow().state());
    }

    @Test
    void clearPlayerRemovesEveryProviderAndInvalidatesPendingGenerations() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation oldManGeneration = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionCache.Generation chiefGeneration =
                cache.nextGeneration(PLAYER_ID, "village-chief", LIFE_ID);
        cache.publish(PLAYER_ID, "old-man", oldManGeneration, state(1, 1, "active"), FETCHED_AT);
        cache.publish(PLAYER_ID, "village-chief", chiefGeneration, state(1, 1, "active", "village-chief"), FETCHED_AT);

        cache.clearPlayer(PLAYER_ID);

        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
        assertTrue(cache.findLastConfirmed(PLAYER_ID, "village-chief").isEmpty());
        assertFalse(cache.publish(PLAYER_ID, "old-man", oldManGeneration, state(2, 2, "completed"), FETCHED_AT));
    }

    @Test
    void customTtlIsAvailableForDeterministicCoordinatorTests() {
        QuestInteractionCache cache = new QuestInteractionCache(Duration.ofMillis(50));
        QuestInteractionCache.Generation generation = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        cache.publish(PLAYER_ID, "old-man", generation, state(1, 1, "active"), FETCHED_AT);

        assertTrue(cache.findFresh(PLAYER_ID, "old-man", FETCHED_AT.plusMillis(49)).isPresent());
        assertTrue(cache.findFresh(PLAYER_ID, "old-man", FETCHED_AT.plusMillis(50)).isEmpty());
    }

    @Test
    void lifeReplacementInvalidatesOldGenerationAndHidesOldLifeCosmeticWithoutExplicitClear() {
        QuestInteractionCache cache = new QuestInteractionCache();
        QuestInteractionCache.Generation oldGeneration = cache.nextGeneration(PLAYER_ID, "old-man", LIFE_ID);
        QuestInteractionState oldState = state(5, 5, "active");
        assertTrue(cache.publish(PLAYER_ID, "old-man", oldGeneration, oldState, FETCHED_AT));

        QuestInteractionCache.Generation newGeneration =
                cache.nextGeneration(PLAYER_ID, "old-man", NEXT_LIFE_ID);

        assertTrue(cache.findLastConfirmed(PLAYER_ID, "old-man").isEmpty());
        assertFalse(cache.publish(PLAYER_ID, "old-man", oldGeneration, oldState, FETCHED_AT.plusSeconds(1)));
        assertFalse(cache.publish(
                PLAYER_ID,
                "old-man",
                newGeneration,
                state(1, 0, "available"),
                FETCHED_AT.plusSeconds(1)));
        assertTrue(cache.publish(
                PLAYER_ID,
                "old-man",
                newGeneration,
                state(1, 0, "available", "old-man", NEXT_LIFE_ID),
                FETCHED_AT.plusSeconds(1)));
    }

    private static QuestInteractionState state(long playerRevision, long questRevision, String questState) {
        return state(playerRevision, questRevision, questState, "old-man");
    }

    private static QuestInteractionState state(
            long playerRevision, long questRevision, String questState, String providerId) {
        return state(playerRevision, questRevision, questState, providerId, LIFE_ID);
    }

    private static QuestInteractionState state(
            long playerRevision, long questRevision, String questState, String providerId, UUID lifeId) {
        ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                "first-steps", "初入凡尘", "main", questState, "remind", null, List.of());
        QuestProviderSnapshot provider = new QuestProviderSnapshot(
                providerId, "first-steps:" + questState, List.of(quest), List.of("first-steps"), "first-steps", null);
        return new QuestInteractionState(
                1,
                UUID.fromString("10000000-0000-0000-0000-000000000001"),
                lifeId,
                new QuestRevisionVector(playerRevision, questRevision, "sha256:definitions"),
                List.of(provider),
                null,
                2000);
    }
}
