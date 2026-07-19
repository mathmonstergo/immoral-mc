package com.immortalmc.adapter.storage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import com.immortalmc.adapter.client.StorageSlotSnapshot;
import com.immortalmc.adapter.client.StorageSnapshot;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class RegionalStorageInventoryHolderTest {
    private static final UUID PLAYER_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ACCOUNT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void holderKeepsIdentityAcrossPageUpdatesAndClearsMoveSelection() {
        RegionalStorageInventoryHolder holder = new RegionalStorageInventoryHolder(
                PLAYER_ID,
                ACCOUNT_ID,
                LIFE_ID,
                "qi-field",
                snapshot(1, 7));
        holder.select(3);

        holder.update(snapshot(2, 8));

        assertEquals(2, holder.snapshot().page());
        assertEquals(8, holder.snapshot().revision());
        assertNull(holder.selectedSlot());
        assertThrows(IllegalArgumentException.class, () -> holder.update(snapshot("other-area", 2, 8)));
    }

    @Test
    void holderSerializesOneMutationAtATime() {
        RegionalStorageInventoryHolder holder = new RegionalStorageInventoryHolder(
                PLAYER_ID,
                ACCOUNT_ID,
                LIFE_ID,
                "qi-field",
                snapshot(1, 0));

        assertTrue(holder.beginOperation());
        assertFalse(holder.beginOperation());
        holder.finishOperation();
        assertTrue(holder.beginOperation());
    }

    private static StorageSnapshot snapshot(int page, long revision) {
        return snapshot("qi-field", page, revision);
    }

    private static StorageSnapshot snapshot(String areaId, int page, long revision) {
        return new StorageSnapshot(
                1,
                LIFE_ID,
                areaId,
                "sha256:storage",
                "immortalmc.storage",
                page,
                9,
                45,
                revision,
                List.of(new StorageSlotSnapshot(
                        3,
                        new ItemInstanceSnapshot(
                                1,
                                ITEM_ID,
                                "technique_manual_yinqi",
                                1,
                                "GF_YinqiShu_01",
                                "owned",
                                "storage"))));
    }
}
