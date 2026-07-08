package com.immortalmc.adapter.event;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.List;
import java.util.Objects;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.inventory.EquipmentSlot;

public final class ImmortalEntityInteractionListener implements Listener {
    private final EntityInteractionRegistry registry;
    private final EntityInteractionActionRouter<BukkitEntityInteractionContext> router;
    private final AdapterLogger logger;

    public ImmortalEntityInteractionListener(
            EntityInteractionRegistry registry,
            EntityInteractionActionRouter<BukkitEntityInteractionContext> router,
            AdapterLogger logger) {
        this.registry = Objects.requireNonNull(registry, "registry");
        this.router = Objects.requireNonNull(router, "router");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlayerInteractEntity(PlayerInteractEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }

        Entity entity = event.getRightClicked();
        EntityBinding binding = bindingFor(entity);
        List<EntityInteractionDefinition> interactions = registry.findAll(binding);
        if (interactions.isEmpty()) {
            return;
        }

        event.setCancelled(true);
        Player player = event.getPlayer();
        BukkitEntityInteractionContext context = new BukkitEntityInteractionContext(player, entity);
        for (EntityInteractionDefinition interaction : interactions) {
            boolean routed = router.route(interaction, context);
            if (!routed) {
                logger.warn("entity_interaction_unhandled action="
                        + interaction.action()
                        + " interaction_id="
                        + interaction.id()
                        + " world="
                        + binding.worldName()
                        + " entity_uuid="
                        + binding.entityUuid());
            }
        }
    }

    private static EntityBinding bindingFor(Entity entity) {
        return new EntityBinding(entity.getWorld().getName(), entity.getUniqueId());
    }
}
