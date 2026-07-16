package com.immortalmc.adapter.cultivation;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.TechniqueSnapshot;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class TechniquePresentationTest {
    @Test
    void rendersAuthoritativeAttributesAndEligibility() {
        TechniqueSnapshot technique = new TechniqueSnapshot(
                1,
                UUID.randomUUID(),
                "Gongfa_68726c",
                "冰冻术",
                1,
                "qi",
                "练气",
                List.of("water", "ice"),
                10,
                100,
                2,
                "active");

        assertEquals(
                List.of(
                        "组别: qi",
                        "大境界: 练气",
                        "属性: water, ice",
                        "层数: 2/13",
                        "修为: 10/100",
                        "状态: active"),
                TechniquePresentation.loreLines(technique));
    }

    @Test
    void rendersUniversalAndFullStates() {
        TechniqueSnapshot technique = new TechniqueSnapshot(
                1,
                UUID.randomUUID(),
                "GF_YinqiShu_01",
                "引气术",
                1,
                "qi",
                "练气",
                List.of(),
                100,
                100,
                13,
                "active");

        assertEquals("属性: 通用", TechniquePresentation.loreLines(technique).get(2));
        assertEquals("状态: full", TechniquePresentation.loreLines(technique).get(5));
    }
}
