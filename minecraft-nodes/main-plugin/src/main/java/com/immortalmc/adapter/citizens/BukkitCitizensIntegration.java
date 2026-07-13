package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.interaction.InteractionDebouncer;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.time.Duration;
import java.util.Objects;
import org.bukkit.plugin.java.JavaPlugin;

public final class BukkitCitizensIntegration {
    private BukkitCitizensIntegration() {}

    public static CitizensIntegrationHandle enable(
            JavaPlugin plugin,
            EntityInteractionRegistry registry,
            EntityInteractionActionRouter<BukkitEntityInteractionContext> router,
            AdapterLogger logger) {
        Objects.requireNonNull(plugin, "plugin");
        CitizensNpcResolver resolver = new BukkitCitizensNpcResolver();
        CitizensNpcInteractionHandler handler = new CitizensNpcInteractionHandler(
                registry,
                router,
                logger,
                new InteractionDebouncer(Duration.ofMillis(500), System::nanoTime));
        plugin.getServer().getPluginManager().registerEvents(
                new CitizensNpcInteractionListener(handler),
                plugin);
        return new CitizensIntegrationHandle(
                resolver,
                new BukkitCitizensNpcSelector(),
                new BukkitQuestNpcSource(registry));
    }
}
