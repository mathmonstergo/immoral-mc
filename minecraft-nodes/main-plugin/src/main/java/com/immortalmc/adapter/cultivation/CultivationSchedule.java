package com.immortalmc.adapter.cultivation;

import java.time.Duration;
import java.time.Instant;

final class CultivationSchedule {
    static final long ORDINARY_SECLUSION_CYCLE_TICKS = 20L * 10L;

    private CultivationSchedule() {}

    static long delayTicks(Instant now, Instant completesAt) {
        long remainingMillis = Math.max(0, Duration.between(now, completesAt).toMillis());
        return Math.max(1, (remainingMillis + 49) / 50 + 1);
    }
}
