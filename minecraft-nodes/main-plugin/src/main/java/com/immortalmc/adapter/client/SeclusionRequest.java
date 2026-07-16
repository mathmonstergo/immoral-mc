package com.immortalmc.adapter.client;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record SeclusionRequest(String areaId, List<UUID> techniqueIds) {
    public SeclusionRequest {
        if (areaId == null || areaId.isBlank()) {
            throw new IllegalArgumentException("areaId must be non-blank");
        }
        techniqueIds = List.copyOf(Objects.requireNonNull(techniqueIds, "techniqueIds"));
        if (techniqueIds.isEmpty() || techniqueIds.size() > 5) {
            throw new IllegalArgumentException("techniqueIds must contain one to five techniques");
        }
        if (techniqueIds.stream().anyMatch(Objects::isNull)
                || new HashSet<>(techniqueIds).size() != techniqueIds.size()) {
            throw new IllegalArgumentException("techniqueIds must contain unique UUIDs");
        }
    }
}
