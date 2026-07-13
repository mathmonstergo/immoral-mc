package com.immortalmc.adapter.quest;

import java.util.Objects;
import java.util.UUID;

public record QuestNpcPosition(
        UUID npcId,
        String providerId,
        UUID worldId,
        double x,
        double y,
        double z,
        int chunkX,
        int chunkZ) {
    public QuestNpcPosition {
        Objects.requireNonNull(npcId, "npcId");
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(worldId, "worldId");
    }
}
