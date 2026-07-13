package com.immortalmc.adapter.command;

import com.immortalmc.adapter.citizens.CitizensNpcSelection;
import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;

public final class QuestProviderAdminMessages {
    public String playerOnly() {
        return "Only players can manage Citizens quest providers.";
    }

    public String selectionMissing() {
        return "No Citizens NPC selected. Run /npc select <id|name> first.";
    }

    public String selectedNpcNotSpawned(CitizensNpcSelection selection) {
        return selectedNpc(selection) + " is not spawned. Spawn it before binding a quest provider.";
    }

    public String catalogUnavailable() {
        return "Quest provider templates are unavailable. Run /immortal quest reload and try again.";
    }

    public String providerMissing(String providerId) {
        return "Quest provider template '" + providerId + "' does not exist.";
    }

    public String templatesHeader(QuestProviderCatalog catalog) {
        return "Quest provider templates: "
                + catalog.providers().size()
                + " loaded (revision "
                + catalog.revision()
                + ").";
    }

    public String templateEntry(QuestProviderTemplate provider) {
        return "- "
                + provider.providerId()
                + " ("
                + provider.displayName()
                + ") main="
                + provider.mainQuestIds()
                + " side="
                + provider.sideQuestIds();
    }

    public String bound(
            CitizensNpcSelection selection,
            QuestProviderTemplate provider,
            int totalBindings) {
        return selectedNpc(selection)
                + " bound to quest provider "
                + provider.providerId()
                + " ("
                + provider.displayName()
                + "). Total quest provider bindings: "
                + totalBindings
                + ".";
    }

    public String info(
            CitizensNpcSelection selection,
            EntityInteractionDefinition binding,
            String displayName) {
        String providerId = binding.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY)
                .orElse("unknown");
        return selectedNpc(selection)
                + " uses quest provider "
                + providerId
                + " ("
                + displayName
                + "), binding "
                + binding.id()
                + ".";
    }

    public String notBound(CitizensNpcSelection selection) {
        return selectedNpc(selection) + " has no quest provider binding.";
    }

    public String listHeader(int totalBindings) {
        return "Quest provider bindings: " + totalBindings + " configured.";
    }

    public String listEntry(EntityInteractionDefinition binding, String displayName) {
        return "- "
                + binding.id()
                + " provider="
                + binding.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY).orElse("unknown")
                + " ("
                + displayName
                + ") citizens-id="
                + binding.metadataValue(QuestProviderAdminRunner.CITIZENS_NPC_ID_KEY).orElse("unknown")
                + " citizens-name="
                + binding.metadataValue(QuestProviderAdminRunner.CITIZENS_NPC_NAME_KEY).orElse("unknown")
                + " citizens-uuid="
                + binding.metadataValue(QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY).orElse("missing");
    }

    public String removed(CitizensNpcSelection selection, int totalBindings) {
        return "Quest provider binding removed from "
                + selectedNpc(selection)
                + ". The Citizens NPC was not deleted. Total bindings: "
                + totalBindings
                + ".";
    }

    public String reloading() {
        return "Refreshing quest provider templates from Game Service...";
    }

    public String reloaded(QuestProviderCatalog catalog) {
        return "Quest provider templates refreshed: "
                + catalog.providers().size()
                + " loaded (revision "
                + catalog.revision()
                + ").";
    }

    public String reloadFailed(Throwable error, boolean previousCatalogPreserved) {
        Throwable cause = unwrap(error);
        String preservation = previousCatalogPreserved
                ? " The previous confirmed catalog was preserved."
                : " No confirmed catalog is available.";
        return "Quest provider template refresh failed: " + cause.getMessage() + "." + preservation;
    }

    private static String selectedNpc(CitizensNpcSelection selection) {
        return "Citizens NPC '" + selection.name() + "' (#" + selection.numericId() + ")";
    }

    private static Throwable unwrap(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }
}
