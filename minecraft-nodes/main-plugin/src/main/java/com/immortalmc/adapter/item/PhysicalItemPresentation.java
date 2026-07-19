package com.immortalmc.adapter.item;

import java.util.List;
import java.util.Objects;
import org.bukkit.Material;

public record PhysicalItemPresentation(Material material, String displayName, List<String> lore) {
    public PhysicalItemPresentation {
        Objects.requireNonNull(material, "material");
        if (material == Material.AIR
                || material == Material.CAVE_AIR
                || material == Material.VOID_AIR) {
            throw new IllegalArgumentException("material cannot be air");
        }
        if (displayName == null || displayName.isBlank()) {
            throw new IllegalArgumentException("displayName must be non-blank");
        }
        lore = List.copyOf(Objects.requireNonNull(lore, "lore"));
    }
}
