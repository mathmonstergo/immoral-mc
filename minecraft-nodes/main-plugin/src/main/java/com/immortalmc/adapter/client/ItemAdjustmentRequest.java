package com.immortalmc.adapter.client;

public record ItemAdjustmentRequest(String itemCode, long deltaQuantity) {
    public ItemAdjustmentRequest {
        if (!"foundation_pill".equals(itemCode)) {
            throw new IllegalArgumentException("itemCode must be foundation_pill");
        }
        if (deltaQuantity <= 0 || deltaQuantity > 1_000_000) {
            throw new IllegalArgumentException("deltaQuantity must be between one and one million");
        }
    }
}
