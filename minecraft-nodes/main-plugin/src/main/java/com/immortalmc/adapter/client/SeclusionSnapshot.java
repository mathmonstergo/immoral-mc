package com.immortalmc.adapter.client;

import java.time.Instant;
import java.util.Objects;
import java.util.UUID;

public record SeclusionSnapshot(
        int contractVersion,
        UUID sessionId,
        String status,
        Instant startedAt,
        Instant completesAt,
        long cumulativeGenerated,
        long cumulativeReserveConsumed,
        long cumulativeRetained) {
    public SeclusionSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported seclusion contract version");
        }
        Objects.requireNonNull(sessionId, "sessionId");
        Objects.requireNonNull(startedAt, "startedAt");
        Objects.requireNonNull(completesAt, "completesAt");
        if (status == null || status.isBlank()) {
            throw new IllegalArgumentException("status must be non-blank");
        }
        if (completesAt.isBefore(startedAt)) {
            throw new IllegalArgumentException("completesAt cannot precede startedAt");
        }
        if (cumulativeGenerated < 0 || cumulativeReserveConsumed < 0 || cumulativeRetained < 0) {
            throw new IllegalArgumentException("Seclusion totals must be non-negative");
        }
    }
}
