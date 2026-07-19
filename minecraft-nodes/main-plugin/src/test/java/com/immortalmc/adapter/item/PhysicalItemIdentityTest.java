package com.immortalmc.adapter.item;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PhysicalItemIdentityTest {
    private static final UUID INSTANCE_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");

    @Test
    void genericAndTechniqueItemsHaveExplicitShapes() {
        PhysicalItemIdentity generic = PhysicalItemIdentity.item(INSTANCE_ID, "spirit_stone");
        PhysicalItemIdentity manual = PhysicalItemIdentity.techniqueManual(
                INSTANCE_ID, "manual_yinqi", "GF_YinqiShu_01", 2);

        assertFalse(generic.isTechniqueManual());
        assertTrue(manual.isTechniqueManual());
        assertEquals(Optional.of("GF_YinqiShu_01"), manual.techniqueId());
        assertEquals(Optional.of(2), manual.techniqueVersion());
    }

    @Test
    void rejectsPartialOrInvalidTechniqueMetadata() {
        assertThrows(IllegalArgumentException.class, () -> new PhysicalItemIdentity(
                INSTANCE_ID, "manual", Optional.of("GF_Test"), Optional.empty()));
        assertThrows(IllegalArgumentException.class, () -> PhysicalItemIdentity.techniqueManual(
                INSTANCE_ID, "manual", "GF_Test", 0));
    }
}
