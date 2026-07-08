package com.immortalmc.adapter.interaction;

import java.util.Objects;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public record BukkitEntityInteractionContext(Player player, Entity entity) {
    public BukkitEntityInteractionContext {
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(entity, "entity");
    }
}
