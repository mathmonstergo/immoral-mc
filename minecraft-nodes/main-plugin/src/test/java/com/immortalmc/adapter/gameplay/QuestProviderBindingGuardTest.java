package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.jupiter.api.Test;

class QuestProviderBindingGuardTest {
    private static final UUID ENTITY_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID OTHER_NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000002");

    @Test
    void currentCitizensBindingRemainsValidAndRebindOrRemovalInvalidates() {
        AtomicReference<List<EntityInteractionDefinition>> bindings = new AtomicReference<>(
                List.of(definition("old-man-quests", "old-man", NPC_ID.toString())));
        QuestProviderBindingGuard guard = new QuestProviderBindingGuard(bindings::get);

        assertTrue(guard.isCurrent("old-man-quests", NPC_ID, "old-man"));

        bindings.set(List.of(definition("old-man-quests", "village-chief", NPC_ID.toString())));
        assertFalse(guard.isCurrent("old-man-quests", NPC_ID, "old-man"));

        bindings.set(List.of(definition("old-man-quests", "old-man", OTHER_NPC_ID.toString())));
        assertFalse(guard.isCurrent("old-man-quests", NPC_ID, "old-man"));

        bindings.set(List.of());
        assertFalse(guard.isCurrent("old-man-quests", NPC_ID, "old-man"));
    }

    @Test
    void missingCitizensMetadataFallsBackToBoundEntityUuid() {
        QuestProviderBindingGuard guard = new QuestProviderBindingGuard(
                () -> List.of(definition("plain-npc-quests", "old-man", null)));

        assertTrue(guard.isCurrent("plain-npc-quests", ENTITY_ID, "old-man"));
        assertFalse(guard.isCurrent("plain-npc-quests", NPC_ID, "old-man"));
    }

    @Test
    void invalidCitizensUuidMetadataAndForeignActionsNeverValidate() {
        QuestProviderBindingGuard guard = new QuestProviderBindingGuard(() -> List.of(
                definition("broken-quests", "old-man", "not-a-uuid"),
                new EntityInteractionDefinition(
                        "old-man-dialogue",
                        "npc-dialogue",
                        new EntityBinding("world", ENTITY_ID),
                        "VILLAGER",
                        true,
                        false,
                        Map.of(QuestProviderInteractionAction.PROVIDER_ID_KEY, "old-man"))));

        assertFalse(guard.isCurrent("broken-quests", NPC_ID, "old-man"));
        assertFalse(guard.isCurrent("old-man-dialogue", ENTITY_ID, "old-man"));
    }

    private static EntityInteractionDefinition definition(
            String interactionId, String providerId, String citizensNpcUuid) {
        Map<String, String> metadata = citizensNpcUuid == null
                ? Map.of(QuestProviderInteractionAction.PROVIDER_ID_KEY, providerId)
                : Map.of(
                        QuestProviderInteractionAction.PROVIDER_ID_KEY, providerId,
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, citizensNpcUuid);
        return new EntityInteractionDefinition(
                interactionId,
                QuestProviderInteractionAction.ACTION,
                new EntityBinding("world", ENTITY_ID),
                "VILLAGER",
                true,
                false,
                metadata);
    }
}
