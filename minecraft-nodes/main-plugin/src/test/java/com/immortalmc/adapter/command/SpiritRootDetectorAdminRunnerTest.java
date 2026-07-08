package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.SpiritRootDetectorRegistry;
import com.immortalmc.adapter.content.SpiritRootDetectorRepository;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpiritRootDetectorAdminRunnerTest {
    private static final UUID MINECRAFT_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");

    @Test
    void consoleCannotSetDetector() {
        SpiritRootDetectorAdminRunner runner = runnerWith(new InMemorySpiritRootDetectorRepository());
        List<String> messages = new ArrayList<>();

        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.console(), messages::add);

        assertEquals(List.of("Only players can save spirit-root detector bindings."), messages);
    }

    @Test
    void playerMustLookAtEntityToSetDetector() {
        SpiritRootDetectorAdminRunner runner = runnerWith(new InMemorySpiritRootDetectorRepository());
        List<String> messages = new ArrayList<>();

        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.player(MINECRAFT_UUID), messages::add);

        assertEquals(List.of("Look at an entity within range before saving a spirit-root detector."), messages);
    }

    @Test
    void savingLookedAtEntityPersistsDetectorBinding() {
        InMemorySpiritRootDetectorRepository repository = new InMemorySpiritRootDetectorRepository();
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        EntityBinding target = detector("world", "30000000-0000-0000-0000-000000000001");
        List<String> messages = new ArrayList<>();

        runner.setLookedAtEntityAsDetector(ImmortalCommandSource.player(MINECRAFT_UUID, target), messages::add);

        assertEquals(List.of(target), repository.load());
        assertEquals(
                List.of("Spirit-root detector saved for entity 30000000-0000-0000-0000-000000000001 in world. Total detectors: 1."),
                messages);
    }

    @Test
    void reloadsDetectorBindingsFromRepository() {
        InMemorySpiritRootDetectorRepository repository = new InMemorySpiritRootDetectorRepository();
        repository.replaceWith(List.of(detector("world", "30000000-0000-0000-0000-000000000001")));
        SpiritRootDetectorAdminRunner runner = runnerWith(repository);
        List<String> messages = new ArrayList<>();

        runner.reload(messages::add);

        assertEquals(List.of("Spirit-root detector content reloaded: 1 detector(s)."), messages);
    }

    private static SpiritRootDetectorAdminRunner runnerWith(InMemorySpiritRootDetectorRepository repository) {
        return new SpiritRootDetectorAdminRunner(
                new SpiritRootDetectorRegistry(repository),
                new SpiritRootDetectorAdminMessages(),
                new RecordingAdapterLogger());
    }

    private static EntityBinding detector(String worldName, String entityUuid) {
        return new EntityBinding(worldName, UUID.fromString(entityUuid));
    }

    private static final class InMemorySpiritRootDetectorRepository implements SpiritRootDetectorRepository {
        private List<EntityBinding> bindings = new ArrayList<>();

        @Override
        public List<EntityBinding> load() {
            return List.copyOf(bindings);
        }

        @Override
        public void save(List<EntityBinding> bindings) {
            this.bindings = new ArrayList<>(bindings);
        }

        void replaceWith(List<EntityBinding> bindings) {
            this.bindings = new ArrayList<>(bindings);
        }
    }
}
