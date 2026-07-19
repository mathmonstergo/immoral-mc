package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.UUID;

public record ItemInstanceSnapshot(
        int contractVersion,
        UUID itemInstanceId,
        String itemCode,
        int definitionVersion,
        String techniqueId,
        String status,
        String location) {
    public ItemInstanceSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported item contract version");
        }
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        requireText(itemCode, "itemCode");
        requireText(status, "status");
        if (definitionVersion <= 0) {
            throw new IllegalArgumentException("definitionVersion must be positive");
        }
        if (techniqueId != null && techniqueId.isBlank()) {
            throw new IllegalArgumentException("techniqueId must be null or non-blank");
        }
        switch (status) {
            case "pending_delivery", "consumed" -> {
                if (location != null) {
                    throw new IllegalArgumentException("Non-owned item cannot include a location");
                }
            }
            case "owned" -> {
                if (!"inventory".equals(location) && !"storage".equals(location)) {
                    throw new IllegalArgumentException("Owned item location must be inventory or storage");
                }
            }
            default -> throw new IllegalArgumentException("Unknown item status: " + status);
        }
    }

    public boolean isOwnedInventory() {
        return "owned".equals(status) && "inventory".equals(location);
    }

    public boolean isPendingDelivery() {
        return "pending_delivery".equals(status);
    }

    public boolean isTechniqueManual() {
        return techniqueId != null && !techniqueId.isBlank();
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
    }
}
