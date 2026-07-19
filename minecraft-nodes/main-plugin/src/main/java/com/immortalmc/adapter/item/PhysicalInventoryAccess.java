package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;

/** Bukkit inventory boundary for authoritative physical item instances. */
public interface PhysicalInventoryAccess {
    Optional<PhysicalItemIdentity> identity(ItemStack item);

    ItemStack create(ItemInstanceSnapshot snapshot);

    List<UUID> instanceIds(PlayerInventory inventory);

    boolean contains(PlayerInventory inventory, UUID itemInstanceId);

    boolean add(PlayerInventory inventory, ItemInstanceSnapshot snapshot);

    boolean remove(PlayerInventory inventory, UUID itemInstanceId);

    int removeUnexpected(PlayerInventory inventory, Set<UUID> authoritativeIds);
}
