package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Objects;
import org.bukkit.plugin.java.JavaPlugin;

public final class CitizensIntegrationLoader {
    private static final String IMPLEMENTATION_CLASS =
            "com.immortalmc.adapter.citizens.BukkitCitizensIntegration";

    private CitizensIntegrationLoader() {}

    public static CitizensIntegrationHandle enableIfAvailable(
            JavaPlugin plugin,
            EntityInteractionRegistry registry,
            EntityInteractionActionRouter<BukkitEntityInteractionContext> router,
            AdapterLogger logger) {
        Objects.requireNonNull(plugin, "plugin");
        if (!plugin.getServer().getPluginManager().isPluginEnabled("Citizens")) {
            return CitizensIntegrationHandle.unavailable();
        }

        try {
            Class<?> implementation = Class.forName(
                    IMPLEMENTATION_CLASS,
                    true,
                    CitizensIntegrationLoader.class.getClassLoader());
            Method enable = implementation.getMethod(
                    "enable",
                    JavaPlugin.class,
                    EntityInteractionRegistry.class,
                    EntityInteractionActionRouter.class,
                    AdapterLogger.class);
            return (CitizensIntegrationHandle) enable.invoke(null, plugin, registry, router, logger);
        } catch (InvocationTargetException exception) {
            throw new IllegalStateException("Citizens integration failed to enable", exception.getCause());
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Citizens integration implementation is unavailable", exception);
        }
    }
}
