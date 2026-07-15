package com.immortalmc.adapter.mythicmobs;

import com.immortalmc.adapter.combat.CombatAttributionTracker;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.time.Clock;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Function;
import org.bukkit.plugin.java.JavaPlugin;

public final class BukkitMythicMobsIntegration {
    private BukkitMythicMobsIntegration() {}

    public static MythicMobsIntegrationHandle enable(
            JavaPlugin plugin,
            String serverId,
            CombatAttributionTracker tracker,
            Function<MythicMobDeathSnapshot, CompletableFuture<Boolean>> snapshotSink,
            AdapterLogger logger,
            Clock clock) {
        Objects.requireNonNull(plugin, "plugin");
        MythicMobDeathListener listener = new MythicMobDeathListener(
                serverId,
                tracker,
                snapshotSink,
                logger,
                clock);
        plugin.getServer().getPluginManager().registerEvents(listener, plugin);
        return MythicMobsIntegrationHandle.available(listener);
    }
}
