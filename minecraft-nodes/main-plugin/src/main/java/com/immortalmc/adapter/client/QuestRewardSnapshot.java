package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record QuestRewardSnapshot(
        UUID grantId,
        String rewardId,
        String kind,
        String status,
        String itemCode,
        Integer quantity,
        List<UUID> itemInstanceIds,
        Integer cultivationAmount,
        long appliedAmount,
        long pendingAmount) {
    public QuestRewardSnapshot {
        Objects.requireNonNull(grantId, "grantId");
        Objects.requireNonNull(rewardId, "rewardId");
        Objects.requireNonNull(kind, "kind");
        Objects.requireNonNull(status, "status");
        itemInstanceIds = List.copyOf(Objects.requireNonNull(itemInstanceIds, "itemInstanceIds"));
        if (appliedAmount < 0 || pendingAmount < 0) {
            throw new IllegalArgumentException("Quest reward amounts must be non-negative");
        }
        if (!"applied".equals(status) && !"pending".equals(status)) {
            throw new IllegalArgumentException("Unknown quest reward status: " + status);
        }
        if (("applied".equals(status) && pendingAmount != 0)
                || ("pending".equals(status) && pendingAmount == 0)) {
            throw new IllegalArgumentException("Quest reward status does not match its pending amount");
        }
        switch (kind) {
            case "fixed_item" -> {
                if (itemCode == null
                        || itemCode.isBlank()
                        || quantity == null
                        || quantity <= 0
                        || itemInstanceIds.size() != quantity
                        || cultivationAmount != null
                        || appliedAmount != 0
                        || pendingAmount != quantity) {
                    throw new IllegalArgumentException("Fixed-item quest reward shape is invalid");
                }
            }
            case "unrefined_cultivation" -> {
                if (itemCode != null
                        || quantity != null
                        || !itemInstanceIds.isEmpty()
                        || cultivationAmount == null
                        || cultivationAmount <= 0
                        || appliedAmount + pendingAmount != cultivationAmount) {
                    throw new IllegalArgumentException("Cultivation quest reward shape is invalid");
                }
            }
            default -> throw new IllegalArgumentException("Unknown quest reward kind: " + kind);
        }
    }
}
