package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record StorageSnapshot(
        int contractVersion,
        UUID lifeId,
        String areaId,
        String catalogRevision,
        String permission,
        int page,
        int pageCount,
        int itemSlotsPerPage,
        long revision,
        List<StorageSlotSnapshot> slots) {
    public StorageSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported storage contract version");
        }
        Objects.requireNonNull(lifeId, "lifeId");
        requireText(areaId, "areaId");
        requireText(catalogRevision, "catalogRevision");
        requireText(permission, "permission");
        if (page < 1 || pageCount < 1 || page > pageCount) {
            throw new IllegalArgumentException("Storage page is outside the catalog");
        }
        if (itemSlotsPerPage < 1 || itemSlotsPerPage > 45 || revision < 0) {
            throw new IllegalArgumentException("Storage snapshot bounds are invalid");
        }
        slots = List.copyOf(Objects.requireNonNull(slots, "slots"));
        if (slots.stream().map(StorageSlotSnapshot::slot).distinct().count() != slots.size()) {
            throw new IllegalArgumentException("Storage snapshot contains duplicate slots");
        }
        if (slots.stream().anyMatch(slot -> slot.slot() >= itemSlotsPerPage)) {
            throw new IllegalArgumentException("Storage snapshot contains a slot outside configured capacity");
        }
        if (slots.stream().anyMatch(slot -> !"owned".equals(slot.item().status())
                || !"storage".equals(slot.item().location()))) {
            throw new IllegalArgumentException("Storage snapshot contains a non-storage item");
        }
    }

    public StorageSlotSnapshot slot(int slot) {
        return slots.stream().filter(value -> value.slot() == slot).findFirst().orElse(null);
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
    }
}
