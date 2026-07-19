package com.immortalmc.adapter.client;

import java.util.Objects;

public record ItemDeliveryConfirmationSnapshot(
        int contractVersion,
        ItemInstanceSnapshot item) {
    public ItemDeliveryConfirmationSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported item delivery contract version");
        }
        Objects.requireNonNull(item, "item");
    }
}
