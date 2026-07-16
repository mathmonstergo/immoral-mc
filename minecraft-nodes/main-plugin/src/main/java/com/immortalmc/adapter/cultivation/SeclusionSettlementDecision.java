package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.SeclusionSnapshot;

record SeclusionSettlementDecision(String playerMessage, boolean retry) {
    static SeclusionSettlementDecision from(SeclusionSnapshot snapshot) {
        return switch (snapshot.status()) {
            case "completed" -> new SeclusionSettlementDecision("闭关完成，修为已炼化。", false);
            case "active", "pending" -> new SeclusionSettlementDecision(
                    "本次闭关已结算，仍可继续炼化，稍后将自动再次结算。",
                    true);
            default -> new SeclusionSettlementDecision("闭关状态已更新：" + snapshot.status(), false);
        };
    }
}
