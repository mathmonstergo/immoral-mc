package com.immortalmc.adapter.quest;

import java.util.Objects;
import java.util.UUID;

public record QuestPlayerPosition(
        UUID playerId,
        UUID accountId,
        UUID lifeId,
        UUID worldId,
        double x,
        double y,
        double z,
        int chunkX,
        int chunkZ) {
    public QuestPlayerPosition {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(lifeId, "lifeId");
        Objects.requireNonNull(worldId, "worldId");
    }
}
