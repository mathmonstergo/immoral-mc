package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class QuestOfferSessionStoreTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID WORLD_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");
    private static final Instant NOW = Instant.parse("2026-07-13T12:00:00Z");

    @Test
    void replacesOldSessionAndRemovesItsLabelExactlyOnce() {
        QuestOfferSessionStore store = new QuestOfferSessionStore();
        RecordingLabel first = new RecordingLabel();
        RecordingLabel second = new RecordingLabel();

        QuestOfferSession old = store.start(
                PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 1, 2, 3, NOW, first);
        QuestOfferSession replacement = store.start(
                PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 1, 2, 3, NOW, second);

        assertFalse(store.isCurrent(old.token()));
        assertTrue(store.isCurrent(replacement.token()));
        assertEquals(1, first.removals.get());
        assertEquals(0, second.removals.get());
    }

    @Test
    void completionMovesCurrentSessionToAwaitingAndUpdatesSameLabel() {
        QuestOfferSessionStore store = new QuestOfferSessionStore();
        RecordingLabel label = new RecordingLabel();
        QuestOfferSession session = store.start(
                PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 1, 2, 3, NOW, label);

        assertTrue(store.markAwaitingConfirmation(session.token(), NOW.plusSeconds(3)));

        QuestOfferSession current = store.find(PLAYER_ID).orElseThrow();
        assertEquals(QuestOfferSession.Phase.AWAITING_CONFIRMATION, current.phase());
        assertEquals(NOW.plusSeconds(23), current.expiresAt());
        assertEquals(1, label.awaitingUpdates.get());
        assertEquals(0, label.removals.get());
    }

    @Test
    void cancelAndClearAreIdempotentAndNeverCreateQuestProgress() {
        QuestOfferSessionStore store = new QuestOfferSessionStore();
        RecordingLabel label = new RecordingLabel();
        QuestOfferSession session = store.start(
                PLAYER_ID, NPC_ID, "old-man", "first-steps", WORLD_ID, 1, 2, 3, NOW, label);

        assertTrue(store.cancel(session.token()));
        assertFalse(store.cancel(session.token()));
        store.clearPlayer(PLAYER_ID);

        assertTrue(store.find(PLAYER_ID).isEmpty());
        assertEquals(1, label.removals.get());
    }

    private static final class RecordingLabel implements QuestOfferLabel {
        private final AtomicInteger awaitingUpdates = new AtomicInteger();
        private final AtomicInteger removals = new AtomicInteger();

        @Override
        public void showAwaitingConfirmation() {
            awaitingUpdates.incrementAndGet();
        }

        @Override
        public void remove() {
            removals.incrementAndGet();
        }
    }
}
