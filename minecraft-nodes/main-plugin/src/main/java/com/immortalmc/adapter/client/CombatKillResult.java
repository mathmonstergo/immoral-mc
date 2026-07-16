package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public record CombatKillResult(
        UUID eventId,
        String outcome,
        UUID killEventId,
        UUID lifeId,
        Long configuredRewardAmount,
        Long creditedCultivationAmount,
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
                && (lifeId == null
                        || configuredRewardAmount == null
                        || creditedCultivationAmount == null
                        || unrefinedBalance == null)) {
            throw new IllegalArgumentException("Accepted combat result is missing reward fields");
        }
        if (configuredRewardAmount != null && configuredRewardAmount <= 0) {
            throw new IllegalArgumentException("configuredRewardAmount must be positive");
        }
        if (creditedCultivationAmount != null && creditedCultivationAmount < 0) {
            throw new IllegalArgumentException("creditedCultivationAmount must be non-negative");
        }
        if (unrefinedBalance != null && unrefinedBalance < 0) {
            throw new IllegalArgumentException("unrefinedBalance must be non-negative");
        }
        boolean hasConfigured = configuredRewardAmount != null;
        boolean hasCredited = creditedCultivationAmount != null;
        boolean hasBalance = unrefinedBalance != null;
        if ("duplicate".equals(outcome) && (hasConfigured || hasCredited || hasBalance)
                && !(hasConfigured && hasCredited && hasBalance)) {
            throw new IllegalArgumentException("Duplicate combat reward fields must be all present or all absent");
        }
        if (Set.of("not_rewardable", "account_not_found", "current_life_unavailable").contains(outcome)
                && (hasConfigured || hasCredited || hasBalance)) {
            throw new IllegalArgumentException("No-reward combat result cannot include reward fields");
        }
    }

}
