package com.immortalmc.adapter.mythicmobs;

import com.immortalmc.adapter.combat.CombatAttributionTracker;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.time.Clock;
import java.util.Objects;
import java.util.function.Consumer;
import org.bukkit.plugin.java.JavaPlugin;

public final class MythicMobsIntegrationLoader {
    private static final String IMPLEMENTATION_CLASS =
            "com.immortalmc.adapter.mythicmobs.BukkitMythicMobsIntegration";

    private MythicMobsIntegrationLoader() {}

    public static MythicMobsIntegrationHandle enableIfAvailable(
            JavaPlugin plugin,
            String serverId,
            CombatAttributionTracker tracker,
            Consumer<MythicMobDeathSnapshot> snapshotSink,
            AdapterLogger logger,
            Clock clock) {
        return enableIfAvailable(
                plugin,
                serverId,
                tracker,
                snapshotSink,
                logger,
                clock,
                IMPLEMENTATION_CLASS);
    }

    static MythicMobsIntegrationHandle enableIfAvailable(
            JavaPlugin plugin,
            String serverId,
            CombatAttributionTracker tracker,
            Consumer<MythicMobDeathSnapshot> snapshotSink,
            AdapterLogger logger,
            Clock clock,
            String implementationClass) {
        Objects.requireNonNull(plugin, "plugin");
        Objects.requireNonNull(logger, "logger");
        if (!plugin.getServer().getPluginManager().isPluginEnabled("MythicMobs")) {
            logger.info("mythicmobs_integration_unavailable");
            return MythicMobsIntegrationHandle.unavailable();
        }

        try {
            Class<?> implementation = Class.forName(
                    implementationClass,
                    true,
                    MythicMobsIntegrationLoader.class.getClassLoader());
            Method enable = implementation.getMethod(
                    "enable",
                    JavaPlugin.class,
                    String.class,
                    CombatAttributionTracker.class,
                    Consumer.class,
                    AdapterLogger.class,
                    Clock.class);
            MythicMobsIntegrationHandle handle = (MythicMobsIntegrationHandle) enable.invoke(
                    null,
                    plugin,
                    serverId,
                    tracker,
                    snapshotSink,
                    logger,
                    clock);
            logger.info("mythicmobs_integration_enabled");
            return handle;
        } catch (InvocationTargetException exception) {
            throw new IllegalStateException(
                    "MythicMobs integration failed to enable",
                    exception.getCause());
        } catch (ReflectiveOperationException | LinkageError exception) {
            throw new IllegalStateException(
                    "MythicMobs 5.12.1 integration is incompatible",
                    exception);
        }
    }
}
