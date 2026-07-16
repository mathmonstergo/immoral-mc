package com.immortalmc.adapter.cultivation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.Optional;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

class CultivationAreaResolverTest {
    @Test
    void resolvesOnlyStableAreaIdForWorldAndInclusiveCuboid() throws Exception {
        YamlConfiguration config = new YamlConfiguration();
        config.loadFromString("""
                cultivation:
                  areas:
                    - area-id: spirit_cave
                      world: world
                      min: {x: 0, y: 40, z: -5}
                      max: {x: 10, y: 80, z: 5}
                """);

        CultivationAreaResolver resolver = CultivationAreaResolver.from(config);

        assertEquals(Optional.of("spirit_cave"), resolver.resolve("world", 0, 40, -5));
        assertEquals(Optional.of("spirit_cave"), resolver.resolve("world", 10, 80, 5));
        assertEquals(Optional.empty(), resolver.resolve("world_nether", 5, 60, 0));
        assertEquals(Optional.empty(), resolver.resolve("world", 11, 60, 0));
    }

    @Test
    void rejectsInvertedOrOverlappingCuboidsInSameWorld() throws Exception {
        assertThrows(IllegalArgumentException.class, () -> resolver("""
                - area-id: bad
                  world: world
                  min: {x: 5, y: 0, z: 0}
                  max: {x: 4, y: 1, z: 1}
                """));
        assertThrows(IllegalArgumentException.class, () -> resolver("""
                - area-id: one
                  world: world
                  min: {x: 0, y: 0, z: 0}
                  max: {x: 5, y: 5, z: 5}
                - area-id: two
                  world: world
                  min: {x: 5, y: 5, z: 5}
                  max: {x: 9, y: 9, z: 9}
                """));
    }

    private static CultivationAreaResolver resolver(String areas) throws Exception {
        YamlConfiguration config = new YamlConfiguration();
        config.loadFromString("cultivation:\n  areas:\n" + areas.indent(4));
        return CultivationAreaResolver.from(config);
    }
}
