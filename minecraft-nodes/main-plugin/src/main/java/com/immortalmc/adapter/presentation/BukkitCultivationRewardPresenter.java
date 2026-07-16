package com.immortalmc.adapter.presentation;

import com.destroystokyo.paper.event.entity.ExperienceOrbMergeEvent;
import com.destroystokyo.paper.event.player.PlayerPickupExperienceEvent;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.CombatKillResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.math.BigDecimal;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Consumer;
import java.util.function.Function;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.entity.ExperienceOrb;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.Plugin;

public final class BukkitCultivationRewardPresenter implements CultivationRewardPresenter, Listener {
    private static final BigDecimal LEVELS_PER_ORB = BigDecimal.TEN;
    private static final int MAX_ORB_COUNT = 12;

    private final NamespacedKey ownerKey;
    private final Function<UUID, Player> playerResolver;
    private final OrbFactory orbFactory;
    private final Consumer<UUID> ownerPickup;
    private final AdapterLogger logger;

    public BukkitCultivationRewardPresenter(
            Plugin plugin,
            Consumer<UUID> ownerPickup,
            AdapterLogger logger) {
        this(
                new NamespacedKey(Objects.requireNonNull(plugin, "plugin"), "cultivation_orb_owner"),
                Bukkit::getPlayer,
                (worldKey, x, y, z) -> {
                    World world = Bukkit.getWorld(worldKey);
                    return world == null
                            ? null
                            : world.spawn(new Location(world, x, y, z), ExperienceOrb.class);
                },
                ownerPickup,
                logger);
    }

    BukkitCultivationRewardPresenter(
            NamespacedKey ownerKey,
            Function<UUID, Player> playerResolver,
            OrbFactory orbFactory,
            Consumer<UUID> ownerPickup,
            AdapterLogger logger) {
        this.ownerKey = Objects.requireNonNull(ownerKey, "ownerKey");
        this.playerResolver = Objects.requireNonNull(playerResolver, "playerResolver");
        this.orbFactory = Objects.requireNonNull(orbFactory, "orbFactory");
        this.ownerPickup = Objects.requireNonNull(ownerPickup, "ownerPickup");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @Override
    public void present(CombatKillEventRequest request, CombatKillResult result) {
        Objects.requireNonNull(request, "request");
        Objects.requireNonNull(result, "result");
        if (!"accepted".equals(result.outcome()) || !request.eventId().equals(result.eventId())) {
            return;
        }
        if (playerResolver.apply(request.killerUuid()) == null) {
            return;
        }
        NamespacedKey worldKey = NamespacedKey.fromString(request.world());
        if (worldKey == null) {
            logger.warn("combat_reward_presentation_world_invalid event_id=" + request.eventId()
                    + " world=" + request.world());
            return;
        }
        int orbCount = visualOrbCount(request.mobLevel());
        for (int index = 0; index < orbCount; index++) {
            ExperienceOrb orb = orbFactory.spawn(worldKey, request.x(), request.y(), request.z());
            if (orb == null) {
                logger.warn("combat_reward_presentation_world_unavailable event_id=" + request.eventId()
                        + " world=" + request.world());
                return;
            }
            orb.setExperience(0);
            orb.setCount(1);
            orb.getPersistentDataContainer()
                    .set(ownerKey, PersistentDataType.STRING, request.killerUuid().toString());
        }
    }

    @EventHandler(ignoreCancelled = true)
    public void onPickup(PlayerPickupExperienceEvent event) {
        ExperienceOrb orb = event.getExperienceOrb();
        String ownerValue = orb.getPersistentDataContainer().get(ownerKey, PersistentDataType.STRING);
        if (ownerValue == null) {
            return;
        }
        event.setCancelled(true);
        UUID ownerId;
        try {
            ownerId = UUID.fromString(ownerValue);
        } catch (IllegalArgumentException error) {
            logger.warn("combat_reward_orb_owner_invalid owner=" + ownerValue, error);
            return;
        }
        if (!ownerId.equals(event.getPlayer().getUniqueId())) {
            return;
        }
        orb.setExperience(0);
        orb.remove();
        ownerPickup.accept(ownerId);
    }

    @EventHandler(ignoreCancelled = true)
    public void onMerge(ExperienceOrbMergeEvent event) {
        if (isCultivationOrb(event.getMergeSource()) || isCultivationOrb(event.getMergeTarget())) {
            event.setCancelled(true);
        }
    }

    static int visualOrbCount(String mobLevel) {
        BigDecimal level = new BigDecimal(mobLevel).max(BigDecimal.ZERO);
        int scaled = level.divideToIntegralValue(LEVELS_PER_ORB).intValueExact() + 1;
        return Math.max(1, Math.min(MAX_ORB_COUNT, scaled));
    }

    private boolean isCultivationOrb(ExperienceOrb orb) {
        return orb.getPersistentDataContainer().has(ownerKey, PersistentDataType.STRING);
    }

    @FunctionalInterface
    interface OrbFactory {
        ExperienceOrb spawn(NamespacedKey worldKey, double x, double y, double z);
    }
}
