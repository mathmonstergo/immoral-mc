package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.UUID;

public record LearnTechniqueSnapshot(
        int contractVersion,
        UUID operationId,
        UUID itemInstanceId,
        UUID lifeTechniqueId,
        String techniqueId,
        String displayName,
        int currentLayer,
        String status) {
    public LearnTechniqueSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported technique learn contract version");
        }
        Objects.requireNonNull(operationId, "operationId");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        Objects.requireNonNull(lifeTechniqueId, "lifeTechniqueId");
        requireText(techniqueId, "techniqueId");
        requireText(displayName, "displayName");
        if (currentLayer != 0 || !"active".equals(status)) {
            throw new IllegalArgumentException("Technique learn must create an active layer-zero technique");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
    }
}
