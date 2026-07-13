package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.citizens.CitizensNpcSelection;
import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class QuestProviderAdminRunnerTest {
    private static final UUID PLAYER_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID NPC_UUID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final EntityInteractionEntity NPC_ENTITY = new EntityInteractionEntity(
            new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
            "PLAYER");

    @Test
    void bindUsesSelectedCitizensIdentityAndSurvivesRegistryReload() {
        InMemoryRepository repository = new InMemoryRepository();
        QuestProviderCatalogCache cache = confirmedCache();
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        QuestProviderAdminRunner runner = runner(registry, cache, CompletableFuture.completedFuture(catalog()));
        CitizensNpcSelection selection = selection(7, "Guide", NPC_UUID, NPC_ENTITY);
        List<String> messages = new ArrayList<>();

        runner.bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, selection), "old-man", messages::add);

        EntityInteractionDefinition saved = repository.load().getFirst();
        assertEquals(QuestProviderInteractionAction.ACTION, saved.action());
        assertEquals(NPC_ENTITY.binding(), saved.binding());
        assertEquals("old-man", saved.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY).orElseThrow());
        assertEquals(NPC_UUID.toString(), saved.metadataValue(
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY)
                .orElseThrow());
        assertEquals("citizens", saved.metadataValue(QuestProviderAdminRunner.TARGET_PROVIDER_KEY).orElseThrow());
        assertEquals("7", saved.metadataValue(QuestProviderAdminRunner.CITIZENS_NPC_ID_KEY).orElseThrow());
        assertEquals("Guide", saved.metadataValue(QuestProviderAdminRunner.CITIZENS_NPC_NAME_KEY).orElseThrow());
        assertEquals(
                List.of("Citizens NPC 'Guide' (#7) bound to quest provider old-man (老村民). "
                        + "Total quest provider bindings: 1."),
                messages);

        EntityInteractionRegistry restarted = new EntityInteractionRegistry(repository);
        restarted.reload();
        assertEquals(
                List.of(saved),
                restarted.findAllByMetadata(
                        QuestProviderInteractionAction.ACTION,
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY,
                        NPC_UUID.toString()));
    }

    @Test
    void rebindReplacesOneNpcWhileOneTemplateCanServeMultipleNpcs() {
        InMemoryRepository repository = new InMemoryRepository();
        QuestProviderCatalogCache cache = new QuestProviderCatalogCache();
        cache.confirm(new QuestProviderCatalog(
                1,
                "sha256:catalog",
                List.of(
                        new QuestProviderTemplate("old-man", "老村民", List.of("first-steps"), List.of()),
                        new QuestProviderTemplate("village-chief", "村长", List.of(), List.of("help")))));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        QuestProviderAdminRunner runner = runner(registry, cache, CompletableFuture.completedFuture(catalog()));
        CitizensNpcSelection first = selection(7, "Guide", NPC_UUID, NPC_ENTITY);
        CitizensNpcSelection second = selection(
                8,
                "Guide Two",
                UUID.fromString("40000000-0000-0000-0000-000000000002"),
                new EntityInteractionEntity(
                        new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000002")),
                        "PLAYER"));

        runner.bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, first), "old-man", ignored -> {});
        runner.bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, first), "village-chief", ignored -> {});
        runner.bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, second), "village-chief", ignored -> {});

        assertEquals(2, repository.load().size());
        assertEquals(
                List.of("village-chief"),
                repository.load().stream()
                        .filter(binding -> binding.metadataValue(QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY)
                                .filter(NPC_UUID.toString()::equals)
                                .isPresent())
                        .map(binding -> binding.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY)
                                .orElseThrow())
                        .toList());
        assertEquals(
                2,
                repository.load().stream()
                        .filter(binding -> binding.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY)
                                .filter("village-chief"::equals)
                                .isPresent())
                        .count());
    }

    @Test
    void unavailableOrUnknownCatalogFailsClosedWithoutChangingExistingBinding() {
        InMemoryRepository repository = new InMemoryRepository();
        EntityInteractionDefinition existing = existingBinding();
        repository.save(List.of(existing));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();
        CitizensNpcSelection selection = selection(7, "Guide", NPC_UUID, NPC_ENTITY);
        List<String> messages = new ArrayList<>();

        runner(registry, new QuestProviderCatalogCache(), CompletableFuture.completedFuture(catalog()))
                .bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, selection), "village-chief", messages::add);
        QuestProviderCatalogCache cache = confirmedCache();
        runner(registry, cache, CompletableFuture.completedFuture(catalog()))
                .bind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, selection), "missing", messages::add);

        assertEquals(List.of(existing), repository.load());
        assertEquals(
                List.of(
                        "Quest provider templates are unavailable. Run /immortal quest reload and try again.",
                        "Quest provider template 'missing' does not exist."),
                messages);
    }

    @Test
    void failedRefreshPreservesPreviousCatalogAndUnbindOnlyRemovesMetadata() {
        InMemoryRepository repository = new InMemoryRepository();
        repository.save(List.of(existingBinding()));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();
        QuestProviderCatalogCache cache = confirmedCache();
        QuestProviderAdminRunner runner = runner(
                registry,
                cache,
                CompletableFuture.failedFuture(new IllegalStateException("offline")));
        CitizensNpcSelection selection = selection(7, "Guide", NPC_UUID, NPC_ENTITY);
        List<String> messages = new ArrayList<>();

        runner.reload(messages::add);
        runner.info(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, selection), messages::add);
        runner.unbind(ImmortalCommandSource.playerWithSelectedNpc(PLAYER_UUID, selection), messages::add);

        assertEquals("sha256:catalog", cache.snapshot().orElseThrow().revision());
        assertEquals(List.of(), repository.load());
        assertEquals(
                List.of(
                        "Refreshing quest provider templates from Game Service...",
                        "Quest provider template refresh failed: offline. The previous confirmed catalog was preserved.",
                        "Citizens NPC 'Guide' (#7) uses quest provider old-man (老村民), binding quest-provider-1.",
                        "Quest provider binding removed from Citizens NPC 'Guide' (#7). "
                                + "The Citizens NPC was not deleted. Total bindings: 0."),
                messages);
    }

    @Test
    void bindRequiresPlayerSelectionAndSpawnedNpc() {
        QuestProviderAdminRunner runner = runner(
                new EntityInteractionRegistry(new InMemoryRepository()),
                confirmedCache(),
                CompletableFuture.completedFuture(catalog()));
        List<String> messages = new ArrayList<>();

        runner.bind(ImmortalCommandSource.console(), "old-man", messages::add);
        runner.bind(ImmortalCommandSource.player(PLAYER_UUID), "old-man", messages::add);
        runner.bind(
                ImmortalCommandSource.playerWithSelectedNpc(
                        PLAYER_UUID,
                        new CitizensNpcSelection(7, "Guide", NPC_UUID, Optional.empty())),
                "old-man",
                messages::add);

        assertEquals(
                List.of(
                        "Only players can manage Citizens quest providers.",
                        "No Citizens NPC selected. Run /npc select <id|name> first.",
                        "Citizens NPC 'Guide' (#7) is not spawned. Spawn it before binding a quest provider."),
                messages);
    }

    private static QuestProviderAdminRunner runner(
            EntityInteractionRegistry registry,
            QuestProviderCatalogCache cache,
            CompletableFuture<QuestProviderCatalog> refresh) {
        return new QuestProviderAdminRunner(
                registry,
                cache,
                () -> refresh,
                new QuestProviderAdminMessages(),
                new RecordingAdapterLogger(),
                Runnable::run);
    }

    private static QuestProviderCatalogCache confirmedCache() {
        QuestProviderCatalogCache cache = new QuestProviderCatalogCache();
        cache.confirm(catalog());
        return cache;
    }

    private static QuestProviderCatalog catalog() {
        return new QuestProviderCatalog(
                1,
                "sha256:catalog",
                List.of(new QuestProviderTemplate("old-man", "老村民", List.of("first-steps"), List.of())));
    }

    private static CitizensNpcSelection selection(
            int id,
            String name,
            UUID persistentUuid,
            EntityInteractionEntity entity) {
        return new CitizensNpcSelection(id, name, persistentUuid, Optional.of(entity));
    }

    private static EntityInteractionDefinition existingBinding() {
        return new EntityInteractionDefinition(
                "quest-provider-1",
                QuestProviderInteractionAction.ACTION,
                NPC_ENTITY.binding(),
                NPC_ENTITY.entityType(),
                true,
                false,
                Map.of(
                        QuestProviderAdminRunner.TARGET_PROVIDER_KEY, QuestProviderAdminRunner.CITIZENS_PROVIDER,
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, NPC_UUID.toString(),
                        QuestProviderInteractionAction.PROVIDER_ID_KEY, "old-man",
                        QuestProviderAdminRunner.CITIZENS_NPC_ID_KEY, "7",
                        QuestProviderAdminRunner.CITIZENS_NPC_NAME_KEY, "Guide"));
    }

    private static final class InMemoryRepository implements EntityInteractionRepository {
        private List<EntityInteractionDefinition> interactions = new ArrayList<>();

        @Override
        public List<EntityInteractionDefinition> load() {
            return List.copyOf(interactions);
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {
            this.interactions = new ArrayList<>(interactions);
        }
    }
}
