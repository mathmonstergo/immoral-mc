package com.immortalmc.adapter.cultivation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.SeclusionSnapshot;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SeclusionSettlementDecisionTest {
    @Test
    void activeSettlementWaitsForMoreReserveAndSchedulesAnotherAttempt() {
        SeclusionSettlementDecision decision = SeclusionSettlementDecision.from(snapshot("active"));

        assertTrue(decision.retry());
        assertEquals("本次闭关已结算，仍可继续炼化，稍后将自动再次结算。", decision.playerMessage());
    }

    @Test
    void completedSettlementStopsScheduling() {
        SeclusionSettlementDecision decision = SeclusionSettlementDecision.from(snapshot("completed"));

        assertFalse(decision.retry());
        assertEquals("闭关完成，修为已炼化。", decision.playerMessage());
    }

    private static SeclusionSnapshot snapshot(String status) {
        Instant startedAt = Instant.parse("2026-07-16T10:00:00Z");
        return new SeclusionSnapshot(
                1,
                UUID.randomUUID(),
                status,
                startedAt,
                startedAt.plusSeconds(60),
                10,
                5,
                5);
    }
}
