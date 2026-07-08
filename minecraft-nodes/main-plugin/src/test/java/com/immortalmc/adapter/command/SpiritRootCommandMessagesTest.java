package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.client.SpiritRootSnapshot;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpiritRootCommandMessagesTest {
    @Test
    void successMessageIncludesVariantFieldsWhenPresent() {
        SpiritRootCommandMessages messages = new SpiritRootCommandMessages();
        SpiritRootDetectionResult result = new SpiritRootDetectionResult(
                UUID.fromString("20000000-0000-0000-0000-000000000001"),
                new SpiritRootSnapshot("variant", "异灵根", List.of("金"), "金雷", "雷"),
                false);

        assertEquals(
                "Spirit root: 异灵根 (variant), elements=金, mutated=金雷, variant=雷",
                messages.success(result));
    }
}
