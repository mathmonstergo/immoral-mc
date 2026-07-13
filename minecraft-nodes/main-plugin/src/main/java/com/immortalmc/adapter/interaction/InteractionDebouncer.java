package com.immortalmc.adapter.interaction;

import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.function.LongSupplier;

public final class InteractionDebouncer {
    private final long windowNanos;
    private final LongSupplier nanoTime;
    private final Map<String, Long> lastAcceptedByKey = new HashMap<>();

    public InteractionDebouncer(Duration window, LongSupplier nanoTime) {
        Objects.requireNonNull(window, "window");
        this.nanoTime = Objects.requireNonNull(nanoTime, "nanoTime");
        if (window.isNegative() || window.isZero()) {
            throw new IllegalArgumentException("window must be positive");
        }
        windowNanos = window.toNanos();
    }

    public synchronized boolean tryAcquire(String key) {
        Objects.requireNonNull(key, "key");
        long now = nanoTime.getAsLong();
        lastAcceptedByKey.entrySet().removeIf(entry -> now - entry.getValue() >= windowNanos);
        Long lastAccepted = lastAcceptedByKey.get(key);
        if (lastAccepted != null && now - lastAccepted < windowNanos) {
            return false;
        }
        lastAcceptedByKey.put(key, now);
        return true;
    }

    synchronized int trackedKeyCount() {
        return lastAcceptedByKey.size();
    }
}
