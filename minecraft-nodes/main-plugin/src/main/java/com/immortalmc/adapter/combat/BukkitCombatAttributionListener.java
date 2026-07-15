package com.immortalmc.adapter.combat;

import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityRemoveEvent;

public final class BukkitCombatAttributionListener implements Listener {
    private final CombatAttributionTracker tracker;
    private final PlayerSessionCache sessions;
    private final Clock clock;
    private final Duration sourceLifetime;

    public BukkitCombatAttributionListener(
            CombatAttributionTracker tracker,
            PlayerSessionCache sessions,
            Clock clock,
            Duration sourceLifetime) {
        this.tracker = Objects.requireNonNull(tracker, "tracker");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.clock = Objects.requireNonNull(clock, "clock");
        this.sourceLifetime = Objects.requireNonNull(sourceLifetime, "sourceLifetime");
        if (sourceLifetime.isNegative() || sourceLifetime.isZero()) {
            throw new IllegalArgumentException("sourceLifetime must be positive");
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageByEntityEvent event) {
        Objects.requireNonNull(event, "event");
        if (event.isCancelled() || !(event.getEntity() instanceof LivingEntity target)) {
            return;
        }
        PlayerOwner owner = resolveOwner(event);
        if (owner == null) {
            return;
        }
        double finalDamage = event.getFinalDamage();
        boolean lethal = finalDamage >= target.getHealth();
        Instant at = clock.instant();
        UUID sourceLifeId = sessions.findByMinecraftUuid(owner.player().getUniqueId())
                .map(PlayerLoginResult::currentLife)
                .map(LifeSnapshot::lifeId)
                .orElse(null);
        tracker.recordDamage(
                target.getUniqueId(),
                new CombatSource(
                        owner.player().getUniqueId(),
                        sourceLifeId,
                        null,
                        null,
                        owner.kind(),
                        at,
                        at.plus(sourceLifetime)),
                finalDamage,
                lethal,
                at);
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onEntityRemoved(EntityRemoveEvent event) {
        tracker.clear(Objects.requireNonNull(event, "event").getEntity().getUniqueId());
    }

    private static PlayerOwner resolveOwner(EntityDamageByEntityEvent event) {
        if (event.getDamager() instanceof Player player) {
            return new PlayerOwner(player, CombatAttributionKind.DIRECT);
        }
        if (event.getDamager() instanceof Projectile projectile
                && projectile.getShooter() instanceof Player player) {
            return new PlayerOwner(player, CombatAttributionKind.PROJECTILE);
        }
        return null;
    }

    private record PlayerOwner(Player player, CombatAttributionKind kind) {}
}
