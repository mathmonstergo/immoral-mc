package com.immortalmc.adapter.client;

import java.util.Objects;

public record StorageSlotSnapshot(int slot, ItemInstanceSnapshot item) {
    public StorageSlotSnapshot {
        if (slot < 0 || slot >= 45) {
            throw new IllegalArgumentException("Storage item slot must be between 0 and 44");
        }
        Objects.requireNonNull(item, "item");
    }
}
