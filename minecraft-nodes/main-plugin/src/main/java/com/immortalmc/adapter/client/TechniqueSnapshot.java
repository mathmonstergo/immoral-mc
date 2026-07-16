package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.UUID;

public record TechniqueSnapshot(
        int contractVersion,
        UUID lifeTechniqueId,
        String techniqueId,
        String displayName,
        int definitionVersion,
        String groupCode,
        String majorRealm,
        long investedAmount,
        long maxInvestment,
        int currentLayer,
        String status) {
    public TechniqueSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported technique contract version");
        }
        Objects.requireNonNull(lifeTechniqueId, "lifeTechniqueId");
        requireText(techniqueId, "techniqueId");
        requireText(displayName, "displayName");
        requireText(groupCode, "groupCode");
        requireText(majorRealm, "majorRealm");
        requireText(status, "status");
        if (definitionVersion <= 0) {
            throw new IllegalArgumentException("definitionVersion must be positive");
        }
        if (investedAmount < 0 || maxInvestment <= 0 || investedAmount > maxInvestment) {
            throw new IllegalArgumentException("Technique investment is outside supported bounds");
        }
        if (currentLayer < 1 || currentLayer > 13) {
            throw new IllegalArgumentException("currentLayer is outside supported bounds");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
    }
}
