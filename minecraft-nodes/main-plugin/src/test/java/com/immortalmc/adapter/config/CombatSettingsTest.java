package com.immortalmc.adapter.config;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.nio.file.Path;
import java.time.Duration;
import org.bukkit.configuration.file.YamlConfiguration;
import org.junit.jupiter.api.Test;

class CombatSettingsTest {
    @Test
    void parsesStrictCombatAndOutboxConfiguration() {
        CombatSettings settings = CombatSettings.from(configuration());

        assertEquals("main-1", settings.serverId());
        assertEquals(Duration.ofSeconds(900), settings.maxSourceAge());
        assertEquals(20_000, settings.maxActiveTargets());
        assertEquals(Path.of("combat-outbox.sqlite3"), settings.outboxFile());
        assertEquals(4096, settings.writerQueueCapacity());
        assertEquals(Duration.ofMillis(5000), settings.busyTimeout());
        assertEquals(Duration.ofMillis(1000), settings.normalDeliveryInterval());
        assertEquals(Duration.ofMillis(5000), settings.highLoadDeliveryInterval());
        assertEquals(17.0, settings.tpsThreshold());
        assertEquals(100, settings.batchSize());
        assertEquals(200, settings.highLoadBatchSize());
        assertEquals(Duration.ofSeconds(30), settings.maxPendingAge());
        assertEquals(Duration.ofSeconds(30), settings.leaseDuration());
        assertEquals(20, settings.maxAttempts());
    }

    @Test
    void missingOrTraversalConfigurationFailsStartup() {
        YamlConfiguration missing = configuration();
        missing.set("server-id", null);
        assertThrows(IllegalArgumentException.class, () -> CombatSettings.from(missing));

        YamlConfiguration traversal = configuration();
        traversal.set("combat.outbox.file", "../shared.sqlite3");
        assertThrows(IllegalArgumentException.class, () -> CombatSettings.from(traversal));
    }

    private static YamlConfiguration configuration() {
        YamlConfiguration config = new YamlConfiguration();
        config.set("server-id", "main-1");
        config.set("combat.attribution.max-source-age-seconds", 900);
        config.set("combat.attribution.max-active-targets", 20_000);
        config.set("combat.outbox.file", "combat-outbox.sqlite3");
        config.set("combat.outbox.writer-queue-capacity", 4096);
        config.set("combat.outbox.busy-timeout-ms", 5000);
        config.set("combat.delivery.normal-interval-ms", 1000);
        config.set("combat.delivery.high-load-interval-ms", 5000);
        config.set("combat.delivery.tps-threshold", 17.0);
        config.set("combat.delivery.batch-size", 100);
        config.set("combat.delivery.high-load-batch-size", 200);
        config.set("combat.delivery.max-pending-age-seconds", 30);
        config.set("combat.delivery.lease-seconds", 30);
        config.set("combat.delivery.max-attempts", 20);
        return config;
    }
}
