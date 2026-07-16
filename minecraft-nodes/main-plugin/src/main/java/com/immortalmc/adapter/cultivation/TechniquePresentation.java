package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.TechniqueSnapshot;
import java.util.List;

final class TechniquePresentation {
    private TechniquePresentation() {}

    static List<String> loreLines(TechniqueSnapshot technique) {
        String attributes = technique.attributeCodes().isEmpty()
                ? "通用"
                : String.join(", ", technique.attributeCodes());
        String status = technique.investedAmount() >= technique.maxInvestment()
                ? "full"
                : technique.status();
        return List.of(
                "组别: " + technique.groupCode(),
                "大境界: " + technique.majorRealm(),
                "属性: " + attributes,
                "层数: " + technique.currentLayer() + "/13",
                "修为: " + technique.investedAmount() + "/" + technique.maxInvestment(),
                "状态: " + status);
    }
}
