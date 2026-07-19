package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

public final class PhysicalPlayerInventory implements PhysicalInventoryAccess {
    private final PhysicalItemCodec codec;
    private final PhysicalItemFactory factory;

    public PhysicalPlayerInventory(PhysicalItemCodec codec, PhysicalItemFactory factory) {
        this.codec = Objects.requireNonNull(codec, "codec");
        this.factory = Objects.requireNonNull(factory, "factory");
    }

    @Override
    public Optional<PhysicalItemIdentity> identity(ItemStack item) {
        return codec.read(item);
    }

    @Override
    public ItemStack create(ItemInstanceSnapshot snapshot) {
        Objects.requireNonNull(snapshot, "snapshot");
        return factory.create(
                PhysicalItemSnapshots.identity(snapshot),
                PhysicalItemSnapshots.presentation(snapshot));
    }

    @Override
    public List<UUID> instanceIds(PlayerInventory inventory) {
        Objects.requireNonNull(inventory, "inventory");
        List<UUID> result = new ArrayList<>();
        Set<UUID> seen = new HashSet<>();
        for (ItemStack item : inventory.getContents()) {
            codec.read(item).ifPresent(identity -> {
                if (seen.add(identity.itemInstanceId())) {
                    result.add(identity.itemInstanceId());
                }
            });
        }
        return List.copyOf(result);
    }

    @Override
    public boolean contains(PlayerInventory inventory, UUID itemInstanceId) {
        Objects.requireNonNull(inventory, "inventory");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        for (ItemStack item : inventory.getContents()) {
            Optional<PhysicalItemIdentity> identity = codec.read(item);
            if (identity.isPresent() && identity.get().itemInstanceId().equals(itemInstanceId)) {
                return true;
            }
        }
        return false;
    }

    @Override
    public boolean add(PlayerInventory inventory, ItemInstanceSnapshot snapshot) {
        Objects.requireNonNull(inventory, "inventory");
        Objects.requireNonNull(snapshot, "snapshot");
        if (contains(inventory, snapshot.itemInstanceId())) {
            return true;
        }
        int slot = inventory.firstEmpty();
        if (slot < 0) {
            return false;
        }
        inventory.setItem(slot, create(snapshot));
        return true;
    }

    @Override
    public boolean remove(PlayerInventory inventory, UUID itemInstanceId) {
        Objects.requireNonNull(inventory, "inventory");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        boolean removed = false;
        ItemStack[] contents = inventory.getContents();
        for (int slot = 0; slot < contents.length; slot++) {
            Optional<PhysicalItemIdentity> identity = codec.read(contents[slot]);
            if (identity.isPresent() && identity.get().itemInstanceId().equals(itemInstanceId)) {
                inventory.setItem(slot, null);
                removed = true;
            }
        }
        return removed;
    }

    @Override
    public int removeUnexpected(PlayerInventory inventory, Set<UUID> authoritativeIds) {
        Objects.requireNonNull(inventory, "inventory");
        Objects.requireNonNull(authoritativeIds, "authoritativeIds");
        int removed = 0;
        Set<UUID> seen = new HashSet<>();
        ItemStack[] contents = inventory.getContents();
        for (int slot = 0; slot < contents.length; slot++) {
            Optional<PhysicalItemIdentity> identity = codec.read(contents[slot]);
            if (identity.isEmpty()) {
                continue;
            }
            UUID itemId = identity.get().itemInstanceId();
            if (!authoritativeIds.contains(itemId) || !seen.add(itemId)) {
                inventory.setItem(slot, null);
                removed++;
            }
        }
        return removed;
    }
}
