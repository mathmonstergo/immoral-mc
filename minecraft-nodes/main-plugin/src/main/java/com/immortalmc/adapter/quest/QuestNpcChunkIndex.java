package com.immortalmc.adapter.quest;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public final class QuestNpcChunkIndex {
    private final Map<ChunkKey, List<QuestNpcPosition>> positionsByChunk = new HashMap<>();
    private final Set<UUID> npcIds = new HashSet<>();

    public void replaceAll(List<QuestNpcPosition> positions) {
        positionsByChunk.clear();
        npcIds.clear();
        for (QuestNpcPosition position : List.copyOf(positions)) {
            ChunkKey key = new ChunkKey(position.worldId(), position.chunkX(), position.chunkZ());
            positionsByChunk.computeIfAbsent(key, ignored -> new ArrayList<>()).add(position);
            npcIds.add(position.npcId());
        }
    }

    public List<QuestNpcPosition> nearby(UUID worldId, int chunkX, int chunkZ) {
        Objects.requireNonNull(worldId, "worldId");
        List<QuestNpcPosition> result = new ArrayList<>();
        for (int x = chunkX - 1; x <= chunkX + 1; x++) {
            for (int z = chunkZ - 1; z <= chunkZ + 1; z++) {
                result.addAll(positionsByChunk.getOrDefault(new ChunkKey(worldId, x, z), List.of()));
            }
        }
        return List.copyOf(result);
    }

    public boolean contains(UUID npcId) {
        return npcIds.contains(Objects.requireNonNull(npcId, "npcId"));
    }

    private record ChunkKey(UUID worldId, int x, int z) {}
}
