package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpiritRootDetectorAdminRunnerTest {
    private static final UUID MINECRAFT_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");

    @Test
    void consoleCannotCreateOrSetOrRemoveDetector() {
        SpiritRootDetectorAdminRunner runner = runnerWith(new InMemoryEntityInteractionRepository());
        List<String> messages = new ArrayList<>();

        runner.createDetector(ImmortalCommandSource.console(), messages::add);
        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.console(), messages::add);
        runner.removeLookedAtDetector(ImmortalCommandSource.console(), messages::add);

        assertEquals(
                List.of(
                        "Only players can manage spirit-root detector entities.",
                        "Only players can manage spirit-root detector entities.",
                        "Only players can manage spirit-root detector entities."),
                messages);
    }

    @Test
    void playerMustLookAtEntityToSetOrRemoveDetector() {
        SpiritRootDetectorAdminRunner runner = runnerWith(new InMemoryEntityInteractionRepository());
        List<String> messages = new ArrayList<>();

        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.player(MINECRAFT_UUID), messages::add);
        runner.removeLookedAtDetector(ImmortalCommandSource.player(MINECRAFT_UUID), messages::add);

        assertEquals(
                List.of(
                        "Look at an entity within range before selecting a spirit-root detector.",
                        "Look at an entity within range before selecting a spirit-root detector."),
                messages);
    }

    @Test
    void savingLookedAtEntityPersistsDetectorDefinition() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        EntityInteractionEntity target = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        List<String> messages = new ArrayList<>();

        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.player(MINECRAFT_UUID, target), messages::add);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "spirit-root-detect-1", "spirit-root-detect", target.binding(), "VILLAGER", true)),
                repository.load());
        assertEquals(
                List.of(
                        "Spirit-root detector spirit-root-detect-1 saved for entity "
                                + "30000000-0000-0000-0000-000000000001 in world. Total detectors: 1."),
                messages);
    }

    @Test
    void createSpawnsAndPersistsDetectorDefinition() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        EntityInteractionEntity spawned = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000010", "VILLAGER");
        List<String> messages = new ArrayList<>();

        runner.createDetector(ImmortalCommandSource.playerWithSpawner(MINECRAFT_UUID, detectorId -> spawned), messages::add);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "spirit-root-detect-1", "spirit-root-detect", spawned.binding(), "VILLAGER", true)),
                repository.load());
        assertEquals(
                List.of("Spirit-root detector spirit-root-detect-1 created as VILLAGER in world. Total detectors: 1."),
                messages);
    }

    @Test
    void listReportsConfiguredDetectors() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity target = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        repository.replaceWith(List.of(new EntityInteractionDefinition(
                "spirit-root-detect-1", "spirit-root-detect", target.binding(), "VILLAGER", true)));
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        List<String> messages = new ArrayList<>();

        runner.reload(ignored -> {});
        runner.listDetectors(messages::add);

        assertEquals(
                List.of(
                        "Spirit-root detectors: 1 configured.",
                        "- spirit-root-detect-1 VILLAGER world/30000000-0000-0000-0000-000000000001 protected=true"),
                messages);
    }

    @Test
    void removeLookedAtDetectorPersistsRemainingDefinitions() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity first = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        EntityInteractionEntity second = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000002", "ARMOR_STAND");
        EntityInteractionDefinition secondDefinition =
                new EntityInteractionDefinition(
                        "spirit-root-detect-2", "spirit-root-detect", second.binding(), "ARMOR_STAND", true);
        repository.replaceWith(List.of(
                new EntityInteractionDefinition(
                        "spirit-root-detect-1", "spirit-root-detect", first.binding(), "VILLAGER", true),
                secondDefinition));
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        List<String> messages = new ArrayList<>();

        runner.reload(ignored -> {});
        runner.removeLookedAtDetector(ImmortalCommandSource.player(MINECRAFT_UUID, first), messages::add);

        assertEquals(List.of(secondDefinition), repository.load());
        assertEquals(List.of("Spirit-root detector spirit-root-detect-1 removed. Total detectors: 1."), messages);
    }

    @Test
    void removeRejectsUnboundLookedAtEntity() {
        SpiritRootDetectorAdminRunner runner = runnerWith(new InMemoryEntityInteractionRepository());
        List<String> messages = new ArrayList<>();

        runner.removeLookedAtDetector(
                ImmortalCommandSource.player(
                        MINECRAFT_UUID,
                        interactionEntity("world", "30000000-0000-0000-0000-000000000001", "VILLAGER")),
                messages::add);

        assertEquals(List.of("The selected entity is not a spirit-root detector."), messages);
    }

    @Test
    void reloadsDetectorDefinitionsFromRepository() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        repository.replaceWith(List.of(interaction(
                "spirit-root-detect-1",
                "spirit-root-detect",
                "world",
                "30000000-0000-0000-0000-000000000001",
                "VILLAGER")));
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        List<String> messages = new ArrayList<>();

        runner.reload(messages::add);

        assertEquals(List.of("Spirit-root detector content reloaded: 1 detector(s)."), messages);
    }

    private static SpiritRootDetectorAdminRunner runnerWith(InMemoryEntityInteractionRepository repository) {
        return new SpiritRootDetectorAdminRunner(
                new EntityInteractionRegistry(repository),
                new SpiritRootDetectorAdminMessages(),
                new RecordingAdapterLogger());
    }

    private static EntityInteractionDefinition interaction(
            String id,
            String action,
            String worldName,
            String entityUuid,
            String entityType) {
        return new EntityInteractionDefinition(id, action, binding(worldName, entityUuid), entityType, true);
    }

    private static EntityInteractionEntity interactionEntity(String worldName, String entityUuid, String entityType) {
        return new EntityInteractionEntity(binding(worldName, entityUuid), entityType);
    }

    private static EntityBinding binding(String worldName, String entityUuid) {
        return new EntityBinding(worldName, UUID.fromString(entityUuid));
    }

    private static final class InMemoryEntityInteractionRepository implements EntityInteractionRepository {
        private List<EntityInteractionDefinition> detectors = new ArrayList<>();

        @Override
        public List<EntityInteractionDefinition> load() {
            return List.copyOf(detectors);
        }

        @Override
        public void save(List<EntityInteractionDefinition> detectors) {
            this.detectors = new ArrayList<>(detectors);
        }

        void replaceWith(List<EntityInteractionDefinition> detectors) {
            this.detectors = new ArrayList<>(detectors);
        }
    }
}
