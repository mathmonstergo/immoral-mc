package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record ItemInstancesSnapshot(
        int contractVersion,
        UUID lifeId,
        List<ItemInstanceSnapshot> items) {
    public ItemInstancesSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported item list contract version");
        }
        Objects.requireNonNull(lifeId, "lifeId");
        items = List.copyOf(Objects.requireNonNull(items, "items"));
    }
}
