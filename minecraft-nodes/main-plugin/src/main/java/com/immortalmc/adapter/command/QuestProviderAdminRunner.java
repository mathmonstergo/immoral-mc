package com.immortalmc.adapter.command;

import com.immortalmc.adapter.citizens.CitizensNpcSelection;
import com.immortalmc.adapter.citizens.CitizensBindingMetadata;
import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.function.Consumer;
import java.util.function.Supplier;

public final class QuestProviderAdminRunner {
    public static final String TARGET_PROVIDER_KEY = CitizensBindingMetadata.TARGET_PROVIDER_KEY;
    public static final String CITIZENS_PROVIDER = CitizensBindingMetadata.TARGET_PROVIDER_VALUE;
    public static final String CITIZENS_NPC_ID_KEY = CitizensBindingMetadata.NPC_ID_KEY;
    public static final String CITIZENS_NPC_NAME_KEY = CitizensBindingMetadata.NPC_NAME_KEY;

    private final EntityInteractionRegistry interactionRegistry;
    private final QuestProviderCatalogCache catalogCache;
    private final Supplier<CompletableFuture<QuestProviderCatalog>> catalogFetcher;
    private final QuestProviderAdminMessages messages;
    private final AdapterLogger logger;
    private final Executor mainThreadExecutor;

    public QuestProviderAdminRunner(
            EntityInteractionRegistry interactionRegistry,
            QuestProviderCatalogCache catalogCache,
            Supplier<CompletableFuture<QuestProviderCatalog>> catalogFetcher,
            QuestProviderAdminMessages messages,
            AdapterLogger logger,
            Executor mainThreadExecutor) {
        this.interactionRegistry = Objects.requireNonNull(interactionRegistry, "interactionRegistry");
        this.catalogCache = Objects.requireNonNull(catalogCache, "catalogCache");
        this.catalogFetcher = Objects.requireNonNull(catalogFetcher, "catalogFetcher");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.mainThreadExecutor = Objects.requireNonNull(mainThreadExecutor, "mainThreadExecutor");
    }

    public void listTemplates(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");
        QuestProviderCatalog catalog = catalogCache.snapshot().orElse(null);
        if (catalog == null) {
            sendMessage.accept(messages.catalogUnavailable());
            return;
        }
        sendMessage.accept(messages.templatesHeader(catalog));
        for (QuestProviderTemplate provider : catalog.providers()) {
            sendMessage.accept(messages.templateEntry(provider));
        }
    }

    public void bind(ImmortalCommandSource source, String providerId, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(sendMessage, "sendMessage");

        CitizensNpcSelection selection = requireSelection(source, sendMessage);
        if (selection == null) {
            return;
        }
        QuestProviderTemplate provider = catalogCache.find(providerId).orElse(null);
        if (catalogCache.snapshot().isEmpty()) {
            sendMessage.accept(messages.catalogUnavailable());
            return;
        }
        if (provider == null) {
            sendMessage.accept(messages.providerMissing(providerId));
            return;
        }
        EntityInteractionEntity entity = selection.spawnedEntity().orElse(null);
        if (entity == null) {
            sendMessage.accept(messages.selectedNpcNotSpawned(selection));
            return;
        }

        interactionRegistry.removeInteractionsByMetadata(
                QuestProviderInteractionAction.ACTION,
                QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY,
                selection.persistentUuid().toString());
        Map<String, String> metadata = new LinkedHashMap<>();
        metadata.put(TARGET_PROVIDER_KEY, CITIZENS_PROVIDER);
        metadata.put(QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, selection.persistentUuid().toString());
        metadata.put(QuestProviderInteractionAction.PROVIDER_ID_KEY, provider.providerId());
        metadata.put(CITIZENS_NPC_ID_KEY, Integer.toString(selection.numericId()));
        metadata.put(CITIZENS_NPC_NAME_KEY, selection.name());
        String id = interactionRegistry.nextId(QuestProviderInteractionAction.ACTION);
        EntityInteractionDefinition saved = interactionRegistry.saveInteraction(
                id,
                QuestProviderInteractionAction.ACTION,
                entity,
                false,
                metadata);
        int totalBindings = interactionRegistry.listByAction(QuestProviderInteractionAction.ACTION).size();
        logger.info("quest_provider_bound minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + saved.id()
                + " provider_id="
                + provider.providerId()
                + " citizens_npc_id="
                + selection.numericId()
                + " citizens_npc_uuid="
                + selection.persistentUuid()
                + " total_bindings="
                + totalBindings);
        sendMessage.accept(messages.bound(selection, provider, totalBindings));
    }

    public void info(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");
        CitizensNpcSelection selection = requireSelection(source, sendMessage);
        if (selection == null) {
            return;
        }
        EntityInteractionDefinition binding = findBinding(selection);
        if (binding == null) {
            sendMessage.accept(messages.notBound(selection));
            return;
        }
        sendMessage.accept(messages.info(selection, binding, displayName(binding)));
    }

    public void listBindings(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");
        List<EntityInteractionDefinition> bindings =
                interactionRegistry.listByAction(QuestProviderInteractionAction.ACTION);
        sendMessage.accept(messages.listHeader(bindings.size()));
        for (EntityInteractionDefinition binding : bindings) {
            sendMessage.accept(messages.listEntry(binding, displayName(binding)));
        }
    }

    public void unbind(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");
        CitizensNpcSelection selection = requireSelection(source, sendMessage);
        if (selection == null) {
            return;
        }
        List<EntityInteractionDefinition> removed = interactionRegistry.removeInteractionsByMetadata(
                QuestProviderInteractionAction.ACTION,
                QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY,
                selection.persistentUuid().toString());
        if (removed.isEmpty()) {
            sendMessage.accept(messages.notBound(selection));
            return;
        }
        int totalBindings = interactionRegistry.listByAction(QuestProviderInteractionAction.ACTION).size();
        logger.info("quest_provider_unbound minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " citizens_npc_id="
                + selection.numericId()
                + " citizens_npc_uuid="
                + selection.persistentUuid()
                + " total_bindings="
                + totalBindings);
        sendMessage.accept(messages.removed(selection, totalBindings));
    }

    public void reload(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");
        sendMessage.accept(messages.reloading());
        catalogFetcher.get().whenComplete((catalog, error) -> mainThreadExecutor.execute(() -> {
            if (error != null) {
                boolean preserved = catalogCache.snapshot().isPresent();
                logger.warn("quest_provider_catalog_refresh_failed reason=" + error.getMessage());
                sendMessage.accept(messages.reloadFailed(error, preserved));
                return;
            }
            catalogCache.confirm(catalog);
            logger.info("quest_provider_catalog_refreshed revision="
                    + catalog.revision()
                    + " providers="
                    + catalog.providers().size());
            sendMessage.accept(messages.reloaded(catalog));
        }));
    }

    private CitizensNpcSelection requireSelection(
            ImmortalCommandSource source,
            Consumer<String> sendMessage) {
        if (source.minecraftUuid().isEmpty()) {
            sendMessage.accept(messages.playerOnly());
            return null;
        }
        CitizensNpcSelection selection = source.selectedCitizensNpc().orElse(null);
        if (selection == null) {
            sendMessage.accept(messages.selectionMissing());
        }
        return selection;
    }

    private EntityInteractionDefinition findBinding(CitizensNpcSelection selection) {
        return interactionRegistry.findAllByMetadata(
                        QuestProviderInteractionAction.ACTION,
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY,
                        selection.persistentUuid().toString())
                .stream()
                .findFirst()
                .orElse(null);
    }

    private String displayName(EntityInteractionDefinition binding) {
        String providerId = binding.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY)
                .orElse("unknown");
        return catalogCache.find(providerId)
                .map(QuestProviderTemplate::displayName)
                .orElse("unknown");
    }
}
