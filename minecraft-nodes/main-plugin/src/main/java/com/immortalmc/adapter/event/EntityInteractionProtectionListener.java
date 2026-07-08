package com.immortalmc.adapter.event;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import io.papermc.paper.event.entity.EntityMoveEvent;
import java.util.Objects;
import org.bukkit.entity.Entity;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityCombustEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityDeathEvent;
import org.bukkit.event.entity.EntityTargetEvent;
import org.bukkit.event.entity.EntityTeleportEvent;
import org.bukkit.event.entity.EntityTransformEvent;

public final class EntityInteractionProtectionListener implements Listener {
    private final EntityInteractionRegistry registry;

    public EntityInteractionProtectionListener(EntityInteractionRegistry registry) {
        this.registry = Objects.requireNonNull(registry, "registry");
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityDamage(EntityDamageEvent event) {
        if (isProtected(event.getEntity())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityDeath(EntityDeathEvent event) {
        if (isProtected(event.getEntity())) {
            event.getDrops().clear();
            event.setDroppedExp(0);
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityCombust(EntityCombustEvent event) {
        if (isProtected(event.getEntity())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityTeleport(EntityTeleportEvent event) {
        if (isProtected(event.getEntity())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityMove(EntityMoveEvent event) {
        if (event.hasExplicitlyChangedPosition() && isProtected(event.getEntity())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityTransform(EntityTransformEvent event) {
        if (isProtected(event.getEntity())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onEntityTarget(EntityTargetEvent event) {
        Entity target = event.getTarget();
        if (isProtected(event.getEntity()) || (target != null && isProtected(target))) {
            event.setCancelled(true);
        }
    }

    private boolean isProtected(Entity entity) {
        return registry.isProtected(new EntityBinding(entity.getWorld().getName(), entity.getUniqueId()));
    }
}
