package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class QuestRewardSnapshotTest {
    private static final UUID GRANT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");

    @Test
    void validatesExactFixedItemRewardShape() {
        assertDoesNotThrow(() -> new QuestRewardSnapshot(
                GRANT_ID,
                "starter-manual",
                "fixed_item",
                "pending",
                "technique_manual:GF_YinqiShu_01",
                1,
                List.of(ITEM_ID),
                null,
                0,
                1));
        assertThrows(
                IllegalArgumentException.class,
                () -> new QuestRewardSnapshot(
                        GRANT_ID,
                        "starter-manual",
                        "fixed_item",
                        "pending",
                        "technique_manual:GF_YinqiShu_01",
                        1,
                        List.of(),
                        null,
                        0,
                        1));
    }

    @Test
    void validatesExactCultivationRewardShape() {
        assertDoesNotThrow(() -> new QuestRewardSnapshot(
                GRANT_ID,
                "starter-cultivation",
                "unrefined_cultivation",
                "applied",
                null,
                null,
                List.of(),
                50,
                50,
                0));
        assertThrows(
                NullPointerException.class,
                () -> new QuestRewardSnapshot(
                        GRANT_ID,
                        "starter-cultivation",
                        "unrefined_cultivation",
                        "applied",
                        null,
                        null,
                        null,
                        50,
                        50,
                        0));
    }
}
