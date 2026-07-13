package com.immortalmc.adapter.quest;

import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record QuestOfferSession(
        UUID token,
        UUID playerId,
        UUID npcId,
        String providerId,
        String questId,
        UUID worldId,
        double x,
        double y,
        double z,
        Phase phase,
        Instant startedAt,
        Instant playbackFinishedAt,
        Instant expiresAt,
        QuestOfferLabel label) {
    public QuestOfferSession {
        Objects.requireNonNull(token, "token");
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(npcId, "npcId");
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(questId, "questId");
        Objects.requireNonNull(worldId, "worldId");
        Objects.requireNonNull(phase, "phase");
        Objects.requireNonNull(startedAt, "startedAt");
        Objects.requireNonNull(label, "label");
    }

    public enum Phase {
        PLAYING_OFFER,
        AWAITING_CONFIRMATION
    }
}
