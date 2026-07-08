package com.immortalmc.adapter.event;

import java.util.Objects;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;

public final class ImmortalPlayerJoinListener implements Listener {
    private final PlayerJoinLoginService loginService;

    public ImmortalPlayerJoinListener(PlayerJoinLoginService loginService) {
        this.loginService = Objects.requireNonNull(loginService, "loginService");
    }

    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        loginService.loginOnJoin(player.getUniqueId(), player.getName(), player::sendMessage);
    }
}
