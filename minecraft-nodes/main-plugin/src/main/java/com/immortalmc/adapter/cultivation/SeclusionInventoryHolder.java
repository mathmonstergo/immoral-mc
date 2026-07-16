package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.TechniqueSnapshot;
import java.util.List;
import java.util.UUID;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.jetbrains.annotations.NotNull;

public final class SeclusionInventoryHolder implements InventoryHolder {
    private final UUID playerId;
    private final List<TechniqueSnapshot> techniques;
    private final SeclusionSelection selection;
    private Inventory inventory;

    public SeclusionInventoryHolder(UUID playerId, List<TechniqueSnapshot> techniques) {
        this.playerId = playerId;
        this.techniques = List.copyOf(techniques);
        this.selection = new SeclusionSelection(techniques);
    }

    public UUID playerId() {
        return playerId;
    }

    public List<TechniqueSnapshot> techniques() {
        return techniques;
    }

    public SeclusionSelection selection() {
        return selection;
    }

    public void attach(Inventory inventory) {
        this.inventory = inventory;
    }

    @Override
    public @NotNull Inventory getInventory() {
        if (inventory == null) {
            throw new IllegalStateException("Inventory has not been attached");
        }
        return inventory;
    }
}
