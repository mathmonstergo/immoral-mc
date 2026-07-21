package com.immortalmc.adapter.client;

import java.util.Objects;

public record QuestRewardPreview(
        String rewardId,
        String kind,
        String itemCode,
        Integer quantity,
        Integer cultivationAmount) {
    public QuestRewardPreview {
        Objects.requireNonNull(rewardId, "rewardId");
        Objects.requireNonNull(kind, "kind");
        switch (kind) {
            case "fixed_item" -> {
                if (itemCode == null
                        || itemCode.isBlank()
                        || quantity == null
                        || quantity <= 0
                        || cultivationAmount != null) {
                    throw new IllegalArgumentException("Fixed-item reward preview shape is invalid");
                }
            }
            case "unrefined_cultivation" -> {
                if (itemCode != null
                        || quantity != null
                        || cultivationAmount == null
                        || cultivationAmount <= 0) {
                    throw new IllegalArgumentException("Cultivation reward preview shape is invalid");
                }
            }
            default -> throw new IllegalArgumentException("Unknown quest reward preview kind: " + kind);
        }
    }
}
