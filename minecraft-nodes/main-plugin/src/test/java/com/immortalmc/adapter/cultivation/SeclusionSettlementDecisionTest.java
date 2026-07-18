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
        assertTrue(decision.playerMessage().isEmpty());
    }

    @Test
    void completedSettlementStopsScheduling() {
        SeclusionSettlementDecision decision = SeclusionSettlementDecision.from(snapshot("completed"));

        assertFalse(decision.retry());
        assertEquals("闭关完成，修为已炼化。", decision.playerMessage().orElseThrow());
    }

    private static SeclusionSnapshot snapshot(String status) {
        Instant startedAt = Instant.parse("2026-07-16T10:00:00Z");
        return new SeclusionSnapshot(
                1,
                UUID.randomUUID(),
                status,
                startedAt,
                startedAt.plusSeconds(10),
                10,
                5,
                5);
    }
}
