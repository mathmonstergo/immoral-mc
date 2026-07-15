package com.immortalmc.adapter.outbox;

import com.immortalmc.adapter.client.CombatKillEventRequest;
import java.time.Instant;
import java.util.Objects;

public record KillOutboxRow(
        CombatKillEventRequest request,
        KillOutboxStatus status,
        int attemptCount,
        Instant nextAttemptAt,
        Instant leaseUntil,
        String lastError) {
    public KillOutboxRow {
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(status, "status");
        Objects.requireNonNull(nextAttemptAt, "nextAttemptAt");
        if (attemptCount < 0) {
            throw new IllegalArgumentException("attemptCount must be non-negative");
        }
    }
}
