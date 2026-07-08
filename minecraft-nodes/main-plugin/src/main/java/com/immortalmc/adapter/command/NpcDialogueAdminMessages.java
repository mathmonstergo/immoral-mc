package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.gameplay.NpcDialogueInteractionAction;

public final class NpcDialogueAdminMessages {
    public String playerOnly() {
        return "Only players can manage NPC dialogue entities.";
    }

    public String targetMissing() {
        return "Look at an entity within range before selecting an NPC dialogue entity.";
    }

    public String dialogueMissing(String dialogueId) {
        return "NPC dialogue " + dialogueId + " is not loaded. Create dialogues/" + dialogueId + ".yml and reload.";
    }

    public String bound(EntityInteractionDefinition dialogue, int totalDialogues) {
        return "NPC dialogue "
                + dialogue.id()
                + " bound to "
                + dialogue.metadataValue(NpcDialogueInteractionAction.DIALOGUE_ID_KEY).orElse("unknown")
                + " for entity "
                + dialogue.binding().entityUuid()
                + " in "
                + dialogue.binding().worldName()
                + ". Total NPC dialogues: "
                + totalDialogues
                + ".";
    }

    public String listHeader(int totalDialogues) {
        return "NPC dialogues: " + totalDialogues + " configured.";
    }

    public String listEntry(EntityInteractionDefinition dialogue) {
        return "- "
                + dialogue.id()
                + " "
                + dialogue.metadataValue(NpcDialogueInteractionAction.DIALOGUE_ID_KEY).orElse("unknown")
                + " "
                + dialogue.entityType()
                + " "
                + dialogue.binding().worldName()
                + "/"
                + dialogue.binding().entityUuid()
                + " protected="
                + dialogue.protectedEntity();
    }

    public String removed(EntityInteractionDefinition dialogue, int totalDialogues) {
        return "NPC dialogue "
                + dialogue.id()
                + " removed. Total NPC dialogues: "
                + totalDialogues
                + ".";
    }

    public String notBound() {
        return "The selected entity is not an NPC dialogue.";
    }

    public String reloaded(int totalBindings, int totalDialogueFiles) {
        return "NPC dialogue content reloaded: "
                + totalBindings
                + " binding(s), "
                + totalDialogueFiles
                + " dialogue file(s).";
    }
}
