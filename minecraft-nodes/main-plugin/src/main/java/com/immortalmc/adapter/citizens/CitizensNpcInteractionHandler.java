package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.command.NpcDialogueAdminRunner;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.interaction.InteractionDebouncer;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public final class CitizensNpcInteractionHandler {
    private final EntityInteractionRegistry registry;
    private final EntityInteractionActionRouter<BukkitEntityInteractionContext> router;
    private final AdapterLogger logger;
    private final InteractionDebouncer debouncer;

    public CitizensNpcInteractionHandler(
            EntityInteractionRegistry registry,
            EntityInteractionActionRouter<BukkitEntityInteractionContext> router,
            AdapterLogger logger,
            InteractionDebouncer debouncer) {
        this.registry = Objects.requireNonNull(registry, "registry");
        this.router = Objects.requireNonNull(router, "router");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.debouncer = Objects.requireNonNull(debouncer, "debouncer");
    }

    public boolean handle(UUID citizensNpcUuid, Player player, Entity entity) {
        Objects.requireNonNull(citizensNpcUuid, "citizensNpcUuid");
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(entity, "entity");

        List<EntityInteractionDefinition> interactions = registry
                .findAllByMetadata(NpcDialogueAdminRunner.CITIZENS_NPC_UUID_KEY, citizensNpcUuid.toString())
                .stream()
                .filter(definition -> definition.metadataValue(NpcDialogueAdminRunner.TARGET_PROVIDER_KEY)
                        .filter(NpcDialogueAdminRunner.CITIZENS_PROVIDER::equals)
                        .isPresent())
                .toList();
        if (interactions.isEmpty()) {
            EntityBinding currentBinding = new EntityBinding(entity.getWorld().getName(), entity.getUniqueId());
            interactions = registry.findAll(currentBinding).stream()
                    .filter(definition -> definition.metadataValue(NpcDialogueAdminRunner.TARGET_PROVIDER_KEY).isEmpty())
                    .toList();
        }
        if (interactions.isEmpty()) {
            return false;
        }

        if (interactions.stream().anyMatch(definition -> QuestProviderInteractionAction.ACTION.equals(definition.action()))) {
            interactions = interactions.stream()
                    .filter(definition -> QuestProviderInteractionAction.ACTION.equals(definition.action()))
                    .toList();
        }

        String debounceKey = player.getUniqueId() + ":" + citizensNpcUuid;
        if (!debouncer.tryAcquire(debounceKey)) {
            return true;
        }

        BukkitEntityInteractionContext context = new BukkitEntityInteractionContext(player, entity);
        for (EntityInteractionDefinition interaction : interactions) {
            if (!router.route(interaction, context)) {
                logger.warn("citizens_npc_interaction_unhandled action="
                        + interaction.action()
                        + " interaction_id="
                        + interaction.id()
                        + " citizens_npc_uuid="
                        + citizensNpcUuid);
            }
        }
        return true;
    }
}
