package com.immortalmc.adapter.client;

public record ItemAdjustmentSnapshot(
        int contractVersion,
        String itemCode,
        long deltaQuantity,
        long balanceAfter) {
    public ItemAdjustmentSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported item adjustment contract version");
        }
        if (itemCode == null || itemCode.isBlank()) {
            throw new IllegalArgumentException("itemCode must be non-blank");
        }
        if (deltaQuantity <= 0 || balanceAfter < 0) {
            throw new IllegalArgumentException("Item adjustment values are outside supported bounds");
        }
    }
}
