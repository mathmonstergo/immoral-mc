package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.quest.QuestProviderInventoryController;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Supplier;

/**
 * Revalidates that an open quest GUI still targets the current quest-provider
 * binding. It resolves the bound NPC identity exactly like
 * {@link QuestProviderInteractionAction}: the persistent Citizens NPC UUID
 * metadata when present, otherwise the bound entity UUID.
 */
public final class QuestProviderBindingGuard
        implements QuestProviderInventoryController.ProviderBindingValidator {
    private final Supplier<List<EntityInteractionDefinition>> questProviderBindings;

    public QuestProviderBindingGuard(Supplier<List<EntityInteractionDefinition>> questProviderBindings) {
        this.questProviderBindings = Objects.requireNonNull(questProviderBindings, "questProviderBindings");
    }

    @Override
    public boolean isCurrent(String interactionId, UUID npcId, String providerId) {
        Objects.requireNonNull(interactionId, "interactionId");
        Objects.requireNonNull(npcId, "npcId");
        Objects.requireNonNull(providerId, "providerId");
        for (EntityInteractionDefinition definition : questProviderBindings.get()) {
            if (!QuestProviderInteractionAction.ACTION.equals(definition.action())
                    || !definition.id().equals(interactionId)) {
                continue;
            }
            return definition.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY)
                            .map(providerId::equals)
                            .orElse(false)
                    && npcId.equals(boundNpcId(definition));
        }
        return false;
    }

    private static UUID boundNpcId(EntityInteractionDefinition definition) {
        String value = definition
                .metadataValue(QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY)
                .orElse(null);
        if (value == null) {
            return definition.binding().entityUuid();
        }
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException invalid) {
            return null;
        }
    }
}
