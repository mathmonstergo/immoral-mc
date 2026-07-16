package com.immortalmc.adapter.cultivation;

import java.time.Duration;
import java.time.Instant;

final class CultivationSchedule {
    static final long ACTIVE_SECLUSION_RETRY_TICKS = 20L * 60L;

    private CultivationSchedule() {}

    static long delayTicks(Instant now, Instant completesAt) {
        long remainingMillis = Math.max(0, Duration.between(now, completesAt).toMillis());
        return Math.max(1, (remainingMillis + 49) / 50 + 1);
    }
}
