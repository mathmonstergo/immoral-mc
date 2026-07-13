package com.immortalmc.adapter.content;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class EntityInteractionRegistryTest {
    @Test
    void reloadsInteractionDefinitionsFromRepositoryAndMatchesEntitiesByAction() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionDefinition detector = interaction(
                "detector-1",
                "spirit-root-detect",
                "world",
                "30000000-0000-0000-0000-000000000001",
                "VILLAGER");
        repository.replaceWith(List.of(detector));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);

        int loaded = registry.reload();

        assertEquals(1, loaded);
        assertEquals(List.of(detector), registry.list());
        assertEquals(List.of(detector), registry.listByAction("spirit-root-detect"));
        assertEquals(detector, registry.find(binding("world", "30000000-0000-0000-0000-000000000001")).orElseThrow());
        assertTrue(registry.matches(binding("world", "30000000-0000-0000-0000-000000000001")));
        assertFalse(registry.matches(binding("world_nether", "30000000-0000-0000-0000-000000000001")));
    }

    @Test
    void savingInteractionPersistsDeduplicatedDefinitionsAndUpdatesRegistry() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity entity = interactionEntity("world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);

        EntityInteractionDefinition saved = registry.saveInteraction("spirit-root-detect", entity);
        EntityInteractionDefinition savedAgain = registry.saveInteraction("spirit-root-detect", entity);

        assertEquals("spirit-root-detect-1", saved.id());
        assertEquals(saved, savedAgain);
        assertEquals(List.of(saved), repository.load());
        assertTrue(registry.matches(entity.binding()));
        assertEquals(1, registry.count());
    }

    @Test
    void sameEntityCanHostDifferentActions() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity entity = interactionEntity("world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);

        EntityInteractionDefinition detector = registry.saveInteraction("spirit-root-detect", entity);
        EntityInteractionDefinition dialogue = registry.saveInteraction("npc-dialogue", entity);

        assertEquals(List.of(detector, dialogue), registry.list());
        assertEquals(List.of(dialogue), registry.listByAction("npc-dialogue"));
    }

    @Test
    void savingInteractionPersistsMetadata() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity entity = interactionEntity("world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);

        EntityInteractionDefinition saved = registry.saveInteraction(
                "npc-dialogue-1",
                "npc-dialogue",
                entity,
                false,
                Map.of("dialogue-id", "old-man"));

        assertEquals("old-man", saved.metadataValue("dialogue-id").orElseThrow());
        assertEquals(false, saved.managedEntity());
        assertEquals(List.of(saved), repository.load());
    }

    @Test
    void removingInteractionPersistsRemainingDefinitionsAndUpdatesRegistry() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionDefinition first = interaction(
                "spirit-root-detect-1",
                "spirit-root-detect",
                "world",
                "30000000-0000-0000-0000-000000000001",
                "VILLAGER");
        EntityInteractionDefinition second = interaction(
                "npc-dialogue-1",
                "npc-dialogue",
                "world",
                "30000000-0000-0000-0000-000000000002",
                "VILLAGER");
        repository.replaceWith(List.of(first, second));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();

        assertEquals(
                first,
                registry.removeInteraction("spirit-root-detect", first.binding()).orElseThrow());

        assertFalse(registry.find(first.binding())
                .filter(definition -> definition.action().equals("spirit-root-detect"))
                .isPresent());
        assertTrue(registry.matches(second.binding()));
        assertEquals(List.of(second), repository.load());
    }

    @Test
    void findsCitizensBindingByPersistentMetadataWhenBukkitBindingChanges() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionDefinition dialogue = new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                binding("old-world", "30000000-0000-0000-0000-000000000001"),
                "PLAYER",
                true,
                false,
                Map.of(
                        "target-provider", "citizens",
                        "citizens-npc-uuid", "40000000-0000-0000-0000-000000000001",
                        "dialogue-id", "old-man"));
        repository.replaceWith(List.of(dialogue));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();

        assertEquals(
                List.of(dialogue),
                registry.findAllByMetadata(
                        "npc-dialogue",
                        "citizens-npc-uuid",
                        "40000000-0000-0000-0000-000000000001"));
    }

    @Test
    void removesCitizensBindingByPersistentMetadata() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionDefinition dialogue = new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                binding("old-world", "30000000-0000-0000-0000-000000000001"),
                "PLAYER",
                true,
                false,
                Map.of("citizens-npc-uuid", "40000000-0000-0000-0000-000000000001"));
        repository.replaceWith(List.of(dialogue));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();

        assertEquals(
                List.of(dialogue),
                registry.removeInteractionsByMetadata(
                        "npc-dialogue",
                        "citizens-npc-uuid",
                        "40000000-0000-0000-0000-000000000001"));
        assertEquals(List.of(), repository.load());
    }

    @Test
    void nextIdSkipsExistingActionIds() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        repository.replaceWith(List.of(
                interaction(
                        "spirit-root-detect-1",
                        "spirit-root-detect",
                        "world",
                        "30000000-0000-0000-0000-000000000001",
                        "VILLAGER"),
                interaction(
                        "custom-id",
                        "spirit-root-detect",
                        "world",
                        "30000000-0000-0000-0000-000000000002",
                        "VILLAGER"),
                interaction(
                        "spirit-root-detect-2",
                        "spirit-root-detect",
                        "world",
                        "30000000-0000-0000-0000-000000000003",
                        "VILLAGER")));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();

        assertEquals("spirit-root-detect-3", registry.nextId("spirit-root-detect"));
    }

    private static EntityInteractionDefinition interaction(
            String id,
            String action,
            String worldName,
            String entityUuid,
            String entityType) {
        return new EntityInteractionDefinition(
                id,
                action,
                binding(worldName, entityUuid),
                entityType,
                true);
    }

    private static EntityInteractionEntity interactionEntity(String worldName, String entityUuid, String entityType) {
        return new EntityInteractionEntity(binding(worldName, entityUuid), entityType);
    }

    private static EntityBinding binding(String worldName, String entityUuid) {
        return new EntityBinding(worldName, UUID.fromString(entityUuid));
    }

    private static final class InMemoryEntityInteractionRepository implements EntityInteractionRepository {
        private List<EntityInteractionDefinition> interactions = new ArrayList<>();

        @Override
        public List<EntityInteractionDefinition> load() {
            return List.copyOf(interactions);
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {
            this.interactions = new ArrayList<>(interactions);
        }

        void replaceWith(List<EntityInteractionDefinition> interactions) {
            this.interactions = new ArrayList<>(interactions);
        }
    }
}
