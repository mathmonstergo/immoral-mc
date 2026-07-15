package com.immortalmc.adapter.combat;

import java.time.Duration;
import java.time.Instant;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public final class CombatAttributionTracker {
    private final Duration maxSourceAge;
    private final int maxTargets;
    private final Map<UUID, LethalAttribution> lethalByTarget = new LinkedHashMap<>();

    public CombatAttributionTracker(Duration maxSourceAge, int maxTargets) {
        this.maxSourceAge = Objects.requireNonNull(maxSourceAge, "maxSourceAge");
        if (maxSourceAge.isNegative() || maxSourceAge.isZero()) {
            throw new IllegalArgumentException("maxSourceAge must be positive");
        }
        if (maxTargets <= 0) {
            throw new IllegalArgumentException("maxTargets must be positive");
        }
        this.maxTargets = maxTargets;
    }

    public synchronized void recordDamage(
            UUID target,
            CombatSource source,
            double finalDamage,
            boolean lethal,
            Instant at) {
        Objects.requireNonNull(target, "target");
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(at, "at");
        if (!Double.isFinite(finalDamage) || finalDamage <= 0.0) {
            throw new IllegalArgumentException("finalDamage must be finite and positive");
        }
        removeInvalid(at);
        if (!lethal || !source.isValidAt(at, maxSourceAge)) {
            return;
        }
        lethalByTarget.remove(target);
        lethalByTarget.put(target, new LethalAttribution(source, finalDamage, at));
        evictOverflow();
    }

    public synchronized Optional<LethalAttribution> consumeLethal(UUID target, Instant at) {
        Objects.requireNonNull(target, "target");
        Objects.requireNonNull(at, "at");
        LethalAttribution attribution = lethalByTarget.remove(target);
        if (attribution == null || !attribution.source().isValidAt(at, maxSourceAge)) {
            return Optional.empty();
        }
        return Optional.of(attribution);
    }

    public synchronized void clear(UUID target) {
        lethalByTarget.remove(Objects.requireNonNull(target, "target"));
    }

    public synchronized void clearAll() {
        lethalByTarget.clear();
    }

    synchronized int trackedTargetCount() {
        return lethalByTarget.size();
    }

    private void removeInvalid(Instant at) {
        lethalByTarget.entrySet().removeIf(
                entry -> !entry.getValue().source().isValidAt(at, maxSourceAge));
    }

    private void evictOverflow() {
        Iterator<UUID> oldestFirst = lethalByTarget.keySet().iterator();
        while (lethalByTarget.size() > maxTargets && oldestFirst.hasNext()) {
            oldestFirst.next();
            oldestFirst.remove();
        }
    }
}
