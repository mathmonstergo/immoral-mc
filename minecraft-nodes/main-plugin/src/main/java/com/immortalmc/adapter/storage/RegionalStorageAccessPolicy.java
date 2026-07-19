package com.immortalmc.adapter.storage;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import org.bukkit.entity.Player;

/** Revalidates the current life, area, and permission before every storage action. */
public final class RegionalStorageAccessPolicy {
    private final PlayerSessionCache sessions;

    public RegionalStorageAccessPolicy(PlayerSessionCache sessions) {
        this.sessions = Objects.requireNonNull(sessions, "sessions");
    }

    public boolean allows(
            Player player,
            RegionalStorageInventoryHolder holder,
            String areaId) {
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(holder, "holder");
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        return session != null
                && holder.accountId().equals(session.account().accountId())
                && holder.lifeId().equals(session.currentLife().lifeId())
                && holder.areaId().equals(areaId)
                && player.hasPermission(holder.snapshot().permission());
    }
}
