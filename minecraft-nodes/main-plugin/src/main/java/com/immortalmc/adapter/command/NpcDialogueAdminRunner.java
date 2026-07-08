package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.gameplay.NpcDialogueInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.function.Consumer;

public final class NpcDialogueAdminRunner {
    private final EntityInteractionRegistry interactionRegistry;
    private final NpcDialogueRegistry dialogueRegistry;
    private final NpcDialogueAdminMessages messages;
    private final AdapterLogger logger;

    public NpcDialogueAdminRunner(
            EntityInteractionRegistry interactionRegistry,
            NpcDialogueRegistry dialogueRegistry,
            NpcDialogueAdminMessages messages,
            AdapterLogger logger) {
        this.interactionRegistry = Objects.requireNonNull(interactionRegistry, "interactionRegistry");
        this.dialogueRegistry = Objects.requireNonNull(dialogueRegistry, "dialogueRegistry");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void setLookedAtEntityAsDialogue(
            ImmortalCommandSource source,
            String dialogueId,
            Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(dialogueId, "dialogueId");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("npc_dialogue_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        if (dialogueRegistry.find(dialogueId).isEmpty()) {
            logger.warn("npc_dialogue_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " dialogue_id="
                    + dialogueId
                    + " reason=dialogue_missing");
            sendMessage.accept(messages.dialogueMissing(dialogueId));
            return;
        }
        EntityInteractionEntity entity = source.lookedAtEntity().orElse(null);
        if (entity == null) {
            logger.warn("npc_dialogue_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " dialogue_id="
                    + dialogueId
                    + " reason=target_missing");
            sendMessage.accept(messages.targetMissing());
            return;
        }

        interactionRegistry.removeInteraction(NpcDialogueInteractionAction.ACTION, entity.binding());
        String id = interactionRegistry.nextId(NpcDialogueInteractionAction.ACTION);
        EntityInteractionDefinition saved = interactionRegistry.saveInteraction(
                id,
                NpcDialogueInteractionAction.ACTION,
                entity,
                false,
                Map.of(NpcDialogueInteractionAction.DIALOGUE_ID_KEY, dialogueId));
        int totalDialogues = interactionRegistry.listByAction(NpcDialogueInteractionAction.ACTION).size();
        logger.info("npc_dialogue_bound minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + saved.id()
                + " dialogue_id="
                + dialogueId
                + " world="
                + saved.binding().worldName()
                + " entity_uuid="
                + saved.binding().entityUuid()
                + " entity_type="
                + saved.entityType()
                + " total_dialogues="
                + totalDialogues);
        sendMessage.accept(messages.bound(saved, totalDialogues));
    }

    public void listDialogues(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");

        List<EntityInteractionDefinition> dialogues =
                interactionRegistry.listByAction(NpcDialogueInteractionAction.ACTION);
        sendMessage.accept(messages.listHeader(dialogues.size()));
        for (EntityInteractionDefinition dialogue : dialogues) {
            sendMessage.accept(messages.listEntry(dialogue));
        }
    }

    public void removeLookedAtDialogue(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("npc_dialogue_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        EntityInteractionEntity entity = source.lookedAtEntity().orElse(null);
        if (entity == null) {
            logger.warn("npc_dialogue_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=target_missing");
            sendMessage.accept(messages.targetMissing());
            return;
        }

        EntityInteractionDefinition removed = interactionRegistry
                .removeInteraction(NpcDialogueInteractionAction.ACTION, entity.binding())
                .orElse(null);
        if (removed == null) {
            logger.warn("npc_dialogue_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " world="
                    + entity.binding().worldName()
                    + " entity_uuid="
                    + entity.binding().entityUuid()
                    + " reason=target_not_bound");
            sendMessage.accept(messages.notBound());
            return;
        }

        int totalDialogues = interactionRegistry.listByAction(NpcDialogueInteractionAction.ACTION).size();
        logger.info("npc_dialogue_removed minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + removed.id()
                + " dialogue_id="
                + removed.metadataValue(NpcDialogueInteractionAction.DIALOGUE_ID_KEY).orElse("unknown")
                + " world="
                + removed.binding().worldName()
                + " entity_uuid="
                + removed.binding().entityUuid()
                + " total_dialogues="
                + totalDialogues);
        sendMessage.accept(messages.removed(removed, totalDialogues));
    }

    public void reload(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");

        int totalInteractions = interactionRegistry.reload();
        int totalDialogueFiles = dialogueRegistry.reload();
        int totalBindings = interactionRegistry.listByAction(NpcDialogueInteractionAction.ACTION).size();
        logger.info("npc_dialogue_reloaded total_interactions="
                + totalInteractions
                + " npc_dialogue_bindings="
                + totalBindings
                + " dialogue_files="
                + totalDialogueFiles);
        sendMessage.accept(messages.reloaded(totalBindings, totalDialogueFiles));
    }
}
