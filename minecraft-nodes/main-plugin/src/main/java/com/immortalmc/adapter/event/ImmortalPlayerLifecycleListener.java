package com.immortalmc.adapter.event;

import java.util.Objects;
import java.util.UUID;
import java.util.function.Consumer;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerChangedWorldEvent;
import org.bukkit.event.player.PlayerKickEvent;
import org.bukkit.event.player.PlayerQuitEvent;

public final class ImmortalPlayerLifecycleListener implements Listener {
    private final Consumer<UUID> fullCleanup;
    private final Consumer<UUID> worldChangeCleanup;

    public ImmortalPlayerLifecycleListener(
            Consumer<UUID> fullCleanup,
            Consumer<UUID> worldChangeCleanup) {
        this.fullCleanup = Objects.requireNonNull(fullCleanup, "fullCleanup");
        this.worldChangeCleanup = Objects.requireNonNull(worldChangeCleanup, "worldChangeCleanup");
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        fullCleanup.accept(event.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onKick(PlayerKickEvent event) {
        fullCleanup.accept(event.getPlayer().getUniqueId());
    }

    @EventHandler
    public void onChangedWorld(PlayerChangedWorldEvent event) {
        worldChangeCleanup.accept(event.getPlayer().getUniqueId());
    }
}
