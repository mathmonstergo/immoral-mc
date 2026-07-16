package com.immortalmc.adapter.client;

import java.time.Instant;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public record BreakthroughSnapshot(
        int contractVersion,
        UUID sessionId,
        String status,
        int sourceLevel,
        int targetLevel,
        int pillCount,
        int successBasisPoints,
        int primaryRoll,
        Integer secondaryRoll,
        String outcome,
        Instant startedAt,
        Instant completesAt,
        Instant settledAt) {
    private static final Set<String> OUTCOMES = Set.of("success", "failure_advance", "failure_loss");

    public BreakthroughSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported breakthrough contract version");
        }
        Objects.requireNonNull(sessionId, "sessionId");
        Objects.requireNonNull(startedAt, "startedAt");
        Objects.requireNonNull(completesAt, "completesAt");
        if (status == null || status.isBlank()) {
            throw new IllegalArgumentException("status must be non-blank");
        }
        if (sourceLevel < 1 || sourceLevel > 22 || targetLevel < 1 || targetLevel > 22) {
            throw new IllegalArgumentException("Breakthrough levels are outside supported bounds");
        }
        if (pillCount < 1 || pillCount > 10) {
            throw new IllegalArgumentException("pillCount must be between one and ten");
        }
        if (successBasisPoints < 0 || successBasisPoints > 10_000
                || primaryRoll < 1 || primaryRoll > 10_000
                || (secondaryRoll != null && (secondaryRoll < 1 || secondaryRoll > 10_000))) {
            throw new IllegalArgumentException("Breakthrough probability values are outside supported bounds");
        }
        if (outcome == null || !OUTCOMES.contains(outcome)) {
            throw new IllegalArgumentException("Unsupported breakthrough outcome: " + outcome);
        }
        if (completesAt.isBefore(startedAt) || (settledAt != null && settledAt.isBefore(startedAt))) {
            throw new IllegalArgumentException("Breakthrough timestamps are inconsistent");
        }
    }
}
