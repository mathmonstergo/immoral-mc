package com.immortalmc.adapter.mythicmobs;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.combat.CombatAttributionTracker;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.time.Clock;
import java.time.Duration;
import java.util.ArrayList;
import java.util.concurrent.CompletableFuture;
import org.bukkit.Server;
import org.bukkit.event.Listener;
import org.bukkit.plugin.PluginManager;
import org.bukkit.plugin.java.JavaPlugin;
import org.junit.jupiter.api.Test;

class MythicMobsIntegrationLoaderTest {
    @Test
    void missingMythicMobsLeavesTheIntegrationUnavailable() {
        PluginFixture fixture = plugin(false);
        RecordingAdapterLogger logger = new RecordingAdapterLogger();

        MythicMobsIntegrationHandle handle = MythicMobsIntegrationLoader.enableIfAvailable(
                fixture.plugin(),
                "main-1",
                tracker(),
                snapshot -> CompletableFuture.completedFuture(true),
                logger,
                Clock.systemUTC());

        assertFalse(handle.available());
        verify(fixture.pluginManager(), never()).registerEvents(any(), any());
        assertTrue(logger.messagesAt("info").stream()
                .anyMatch(message -> message.contains("mythicmobs_integration_unavailable")));
    }

    @Test
    void enabledMythicMobsRegistersTheTypedDeathListener() {
        PluginFixture fixture = plugin(true);

        MythicMobsIntegrationHandle handle = MythicMobsIntegrationLoader.enableIfAvailable(
                fixture.plugin(),
                "main-1",
                tracker(),
                snapshot -> CompletableFuture.completedFuture(true),
                new RecordingAdapterLogger(),
                Clock.systemUTC());

        assertTrue(handle.available());
        verify(fixture.pluginManager()).registerEvents(
                any(MythicMobDeathListener.class),
                any(JavaPlugin.class));
    }

    @Test
    void incompatibleIntegrationClassFailsStartupVisibly() {
        PluginFixture fixture = plugin(true);

        assertThrows(
                IllegalStateException.class,
                () -> MythicMobsIntegrationLoader.enableIfAvailable(
                        fixture.plugin(),
                        "main-1",
                        tracker(),
                        snapshot -> CompletableFuture.completedFuture(true),
                        new RecordingAdapterLogger(),
                        Clock.systemUTC(),
                        "com.immortalmc.adapter.mythicmobs.MissingIntegration"));
    }

    private static CombatAttributionTracker tracker() {
        return new CombatAttributionTracker(Duration.ofMinutes(15), 100);
    }

    private static PluginFixture plugin(boolean mythicEnabled) {
        JavaPlugin plugin = mock(JavaPlugin.class);
        Server server = mock(Server.class);
        PluginManager pluginManager = mock(PluginManager.class);
        when(plugin.getServer()).thenReturn(server);
        when(server.getPluginManager()).thenReturn(pluginManager);
        when(pluginManager.isPluginEnabled("MythicMobs")).thenReturn(mythicEnabled);
        return new PluginFixture(plugin, pluginManager);
    }

    private record PluginFixture(JavaPlugin plugin, PluginManager pluginManager) {}
}
