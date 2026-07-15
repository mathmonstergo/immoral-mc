package com.immortalmc.adapter.combat;

import java.time.Instant;
import java.util.Objects;

public record LethalAttribution(CombatSource source, double finalDamage, Instant occurredAt) {
    public LethalAttribution {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(occurredAt, "occurredAt");
        if (!Double.isFinite(finalDamage) || finalDamage <= 0.0) {
            throw new IllegalArgumentException("finalDamage must be finite and positive");
        }
    }
}
