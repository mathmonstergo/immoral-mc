package com.immortalmc.adapter.content;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

class EntityInteractionConfigMapperTest {
    @Test
    void defaultNewPathDoesNotSuppressLegacyDetectorMigration() {
        YamlConfiguration config = new YamlConfiguration();
        config.set("content.spirit-root.detectors", List.of(Map.of(
                "world", "world",
                "entity-uuid", "30000000-0000-0000-0000-000000000001")));
        YamlConfiguration defaults = new YamlConfiguration();
        defaults.set("content.entity-interactions.entries", List.of());
        config.setDefaults(defaults);

        List<EntityInteractionDefinition> loaded = new EntityInteractionConfigMapper().load(config);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "spirit-root-detect-1",
                        "spirit-root-detect",
                        new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                        "UNKNOWN",
                        true,
                        false)),
                loaded);
    }

    @Test
    void explicitNewPathTakesPrecedenceOverLegacyDetectors() {
        YamlConfiguration config = new YamlConfiguration();
        config.set("content.entity-interactions.entries", List.of(Map.of(
                "id", "npc-dialogue-1",
                "action", "npc-dialogue",
                "world", "world",
                "entity-uuid", "30000000-0000-0000-0000-000000000002",
                "entity-type", "VILLAGER",
                "protected", true,
                "managed-entity", true,
                "dialogue-id", "old-man")));
        config.set("content.spirit-root.detectors", List.of(Map.of(
                "world", "world",
                "entity-uuid", "30000000-0000-0000-0000-000000000001")));

        List<EntityInteractionDefinition> loaded = new EntityInteractionConfigMapper().load(config);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "npc-dialogue-1",
                        "npc-dialogue",
                        new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000002")),
                        "VILLAGER",
                        true,
                        true,
                        Map.of("dialogue-id", "old-man"))),
                loaded);
    }

    @Test
    void missingManagedEntityDefaultsToFalse() {
        YamlConfiguration config = new YamlConfiguration();
        config.set("content.entity-interactions.entries", List.of(Map.of(
                "id", "npc-dialogue-1",
                "action", "npc-dialogue",
                "world", "world",
                "entity-uuid", "30000000-0000-0000-0000-000000000002",
                "entity-type", "VILLAGER",
                "protected", true)));

        List<EntityInteractionDefinition> loaded = new EntityInteractionConfigMapper().load(config);

        assertEquals(false, loaded.getFirst().managedEntity());
    }

    @Test
    void dumpWritesManagedEntityFlag() {
        EntityInteractionDefinition interaction = new EntityInteractionDefinition(
                "spirit-root-detect-1",
                "spirit-root-detect",
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "VILLAGER",
                true,
                true);

        List<Map<String, Object>> dumped = new EntityInteractionConfigMapper().dump(List.of(interaction));

        assertEquals(true, dumped.getFirst().get("managed-entity"));
    }

    @Test
    void dumpWritesMetadataFieldsAtEntryTopLevel() {
        EntityInteractionDefinition interaction = new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "VILLAGER",
                true,
                false,
                Map.of("dialogue-id", "old-man"));

        List<Map<String, Object>> dumped = new EntityInteractionConfigMapper().dump(List.of(interaction));

        assertEquals("old-man", dumped.getFirst().get("dialogue-id"));
    }
}
