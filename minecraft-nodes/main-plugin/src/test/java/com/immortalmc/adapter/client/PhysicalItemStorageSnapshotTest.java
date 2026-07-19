package com.immortalmc.adapter.client;

import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PhysicalItemStorageSnapshotTest {
    private static final UUID LIFE_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");

    @Test
    void itemSnapshotRejectsUnknownStateAndInvalidOwnedLocation() {
        assertThrows(
                IllegalArgumentException.class,
                () -> item("legacy", null));
        assertThrows(
                IllegalArgumentException.class,
                () -> item("owned", "ender_chest"));
    }

    @Test
    void storageSnapshotRejectsSlotsOutsideCatalogCapacityAndInventoryItems() {
        assertThrows(
                IllegalArgumentException.class,
                () -> storage(1, new StorageSlotSnapshot(1, item("owned", "storage"))));
        assertThrows(
                IllegalArgumentException.class,
                () -> storage(45, new StorageSlotSnapshot(0, item("owned", "inventory"))));
    }

    @Test
    void moveRequestRejectsCoordinatesOutsideLargeChestItemRange() {
        assertThrows(
                IllegalArgumentException.class,
                () -> StorageMoveRequest.deposit(ITEM_ID, 0, 1, 45));
        assertThrows(
                IllegalArgumentException.class,
                () -> StorageMoveRequest.withdraw(ITEM_ID, 0, 0, 0));
    }

    private static ItemInstanceSnapshot item(String status, String location) {
        return new ItemInstanceSnapshot(
                1,
                ITEM_ID,
                "technique_manual_yinqi",
                1,
                "GF_YinqiShu_01",
                status,
                location);
    }

    private static StorageSnapshot storage(int itemSlots, StorageSlotSnapshot slot) {
        return new StorageSnapshot(
                1,
                LIFE_ID,
                "qi-field",
                "sha256:storage",
                "immortalmc.storage",
                1,
                9,
                itemSlots,
                0,
                List.of(slot));
    }
}
