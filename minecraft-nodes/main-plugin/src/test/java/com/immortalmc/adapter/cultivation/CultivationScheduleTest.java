package com.immortalmc.adapter.cultivation;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class CultivationScheduleTest {
    @Test
    void schedulesAfterTheAuthoritativeCompletionInstant() {
        Instant now = Instant.parse("2026-07-16T10:00:00Z");

        assertEquals(1, CultivationSchedule.delayTicks(now, now.minusMillis(1)));
        assertEquals(2, CultivationSchedule.delayTicks(now, now.plusMillis(1)));
        assertEquals(2, CultivationSchedule.delayTicks(now, now.plusMillis(50)));
        assertEquals(3, CultivationSchedule.delayTicks(now, now.plusMillis(51)));
    }
}
