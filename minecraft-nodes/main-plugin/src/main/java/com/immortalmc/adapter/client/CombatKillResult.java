package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public record CombatKillResult(
        UUID eventId,
        String outcome,
        UUID killEventId,
        UUID lifeId,
        Long rewardAmount,
        Long unrefinedBalance) {
    private static final Set<String> OUTCOMES = Set.of(
            "accepted",
            "duplicate",
            "not_rewardable",
            "account_not_found",
            "current_life_unavailable");

    public CombatKillResult {
        Objects.requireNonNull(eventId, "eventId");
        Objects.requireNonNull(killEventId, "killEventId");
        if (!OUTCOMES.contains(outcome)) {
            throw new IllegalArgumentException("Unsupported combat outcome: " + outcome);
        }
        if ("accepted".equals(outcome)
                && (lifeId == null || rewardAmount == null || unrefinedBalance == null)) {
            throw new IllegalArgumentException("Accepted combat result is missing reward fields");
        }
        if (rewardAmount != null && rewardAmount <= 0) {
            throw new IllegalArgumentException("rewardAmount must be positive");
        }
        if (unrefinedBalance != null && unrefinedBalance < 0) {
            throw new IllegalArgumentException("unrefinedBalance must be non-negative");
        }
    }

}
