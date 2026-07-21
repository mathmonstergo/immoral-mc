package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.citizens.CitizensBindingMetadata;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.quest.QuestProviderGuiOpener;
import java.util.Objects;
import java.util.UUID;

public final class QuestProviderInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "quest-provider";
    public static final String PROVIDER_ID_KEY = "quest-provider-id";
    public static final String CITIZENS_NPC_UUID_KEY = CitizensBindingMetadata.NPC_UUID_KEY;

    private final QuestProviderGuiOpener gui;
    private final AdapterLogger logger;

    public QuestProviderInteractionAction(QuestProviderGuiOpener gui, AdapterLogger logger) {
        this.gui = Objects.requireNonNull(gui, "gui");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @Override
    public void handle(EntityInteractionDefinition definition, BukkitEntityInteractionContext context) {
        String providerId = definition.metadataValue(PROVIDER_ID_KEY).orElse(null);
        if (providerId == null) {
            logger.warn("quest_provider_rejected interaction_id="
                    + definition.id()
                    + " reason=provider_id_missing");
            return;
        }
        UUID npcId;
        try {
            npcId = definition.metadataValue(CITIZENS_NPC_UUID_KEY)
                    .map(UUID::fromString)
                    .orElse(context.entity().getUniqueId());
        } catch (IllegalArgumentException error) {
            logger.warn("quest_provider_rejected interaction_id="
                    + definition.id()
                    + " provider_id="
                    + providerId
                    + " reason=invalid_citizens_npc_uuid");
            return;
        }
        gui.open(context.player(), definition.id(), npcId, providerId);
    }
}
