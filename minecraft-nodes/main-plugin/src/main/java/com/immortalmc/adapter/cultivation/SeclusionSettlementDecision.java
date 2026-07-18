package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.SeclusionSnapshot;
import java.util.Optional;

record SeclusionSettlementDecision(Optional<String> playerMessage, boolean retry) {
    static SeclusionSettlementDecision from(SeclusionSnapshot snapshot) {
        return switch (snapshot.status()) {
            case "completed" -> new SeclusionSettlementDecision(
                    Optional.of("闭关完成，修为已炼化。"), false);
            case "active", "pending" -> new SeclusionSettlementDecision(Optional.empty(), true);
            default -> new SeclusionSettlementDecision(
                    Optional.of("闭关状态已更新：" + snapshot.status()), false);
        };
    }
}
