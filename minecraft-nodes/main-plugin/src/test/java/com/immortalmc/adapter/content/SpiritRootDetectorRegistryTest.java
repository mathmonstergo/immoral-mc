package com.immortalmc.adapter.content;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class SpiritRootDetectorRegistryTest {
    @Test
    void reloadsDetectorBindingsFromRepositoryAndMatchesEntities() {
        InMemorySpiritRootDetectorRepository repository = new InMemorySpiritRootDetectorRepository();
        EntityBinding detector = detector("world", "30000000-0000-0000-0000-000000000001");
        repository.replaceWith(List.of(detector));
        SpiritRootDetectorRegistry registry = new SpiritRootDetectorRegistry(repository);

        int loaded = registry.reload();

        assertEquals(1, loaded);
        assertTrue(registry.matches(detector));
        assertFalse(registry.matches(detector("world_nether", "30000000-0000-0000-0000-000000000001")));
    }

    @Test
    void savingDetectorPersistsDeduplicatedBindingsAndUpdatesRegistry() {
        InMemorySpiritRootDetectorRepository repository = new InMemorySpiritRootDetectorRepository();
        EntityBinding detector = detector("world", "30000000-0000-0000-0000-000000000001");
        SpiritRootDetectorRegistry registry = new SpiritRootDetectorRegistry(repository);

        int savedCount = registry.saveDetector(detector);
        int savedAgainCount = registry.saveDetector(detector);

        assertEquals(1, savedCount);
        assertEquals(1, savedAgainCount);
        assertEquals(List.of(detector), repository.load());
        assertTrue(registry.matches(detector));
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
