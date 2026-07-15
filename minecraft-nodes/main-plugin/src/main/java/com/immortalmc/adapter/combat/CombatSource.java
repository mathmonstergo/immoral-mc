package com.immortalmc.adapter.combat;

import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record CombatSource(
        UUID playerUuid,
        UUID sourceLifeId,
        String techniqueId,
        UUID castId,
        CombatAttributionKind kind,
        Instant createdAt,
        Instant expiresAt) {
    public CombatSource {
        Objects.requireNonNull(playerUuid, "playerUuid");
        Objects.requireNonNull(kind, "kind");
        Objects.requireNonNull(createdAt, "createdAt");
        Objects.requireNonNull(expiresAt, "expiresAt");
        if (techniqueId != null && techniqueId.isBlank()) {
            throw new IllegalArgumentException("techniqueId must be null or non-blank");
        }
        if (!expiresAt.isAfter(createdAt)) {
            throw new IllegalArgumentException("expiresAt must be after createdAt");
        }
    }

    public boolean isValidAt(Instant at, Duration maxSourceAge) {
        Objects.requireNonNull(at, "at");
        Objects.requireNonNull(maxSourceAge, "maxSourceAge");
        if (at.isBefore(createdAt) || !at.isBefore(expiresAt)) {
            return false;
        }
        return Duration.between(createdAt, at).compareTo(maxSourceAge) <= 0;
    }
}
