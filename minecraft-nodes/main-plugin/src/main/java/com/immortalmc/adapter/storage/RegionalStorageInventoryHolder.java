package com.immortalmc.adapter.storage;

import com.immortalmc.adapter.client.StorageSnapshot;
import java.util.Objects;
import java.util.UUID;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.jetbrains.annotations.NotNull;

public final class RegionalStorageInventoryHolder implements InventoryHolder {
    private final UUID playerId;
    private final UUID accountId;
    private final UUID lifeId;
    private final String areaId;
    private StorageSnapshot snapshot;
    private Integer selectedSlot;
    private boolean busy;
    private Inventory inventory;

    public RegionalStorageInventoryHolder(
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            String areaId,
            StorageSnapshot snapshot) {
        this.playerId = Objects.requireNonNull(playerId, "playerId");
        this.accountId = Objects.requireNonNull(accountId, "accountId");
        this.lifeId = Objects.requireNonNull(lifeId, "lifeId");
        this.areaId = requireText(areaId, "areaId");
        this.snapshot = Objects.requireNonNull(snapshot, "snapshot");
        if (!lifeId.equals(snapshot.lifeId()) || !areaId.equals(snapshot.areaId())) {
            throw new IllegalArgumentException("Storage snapshot identity does not match holder");
        }
    }

    public UUID playerId() {
        return playerId;
    }

    public UUID accountId() {
        return accountId;
    }

    public UUID lifeId() {
        return lifeId;
    }

    public String areaId() {
        return areaId;
    }

    public StorageSnapshot snapshot() {
        return snapshot;
    }

    public void update(StorageSnapshot snapshot) {
        Objects.requireNonNull(snapshot, "snapshot");
        if (!lifeId.equals(snapshot.lifeId())
                || !areaId.equals(snapshot.areaId())) {
            throw new IllegalArgumentException("Storage snapshot identity does not match holder");
        }
        this.snapshot = snapshot;
        selectedSlot = null;
    }

    public Integer selectedSlot() {
        return selectedSlot;
    }

    public void select(Integer slot) {
        if (slot != null && (slot < 0 || slot >= snapshot.itemSlotsPerPage())) {
            throw new IllegalArgumentException("Selected storage slot is outside the item range");
        }
        selectedSlot = slot;
    }

    public boolean busy() {
        return busy;
    }

    public boolean beginOperation() {
        if (busy) {
            return false;
        }
        busy = true;
        return true;
    }

    public void finishOperation() {
        busy = false;
    }

    public void attach(Inventory inventory) {
        this.inventory = Objects.requireNonNull(inventory, "inventory");
    }

    @Override
    public @NotNull Inventory getInventory() {
        if (inventory == null) {
            throw new IllegalStateException("Inventory has not been attached");
        }
        return inventory;
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return value;
    }
}
