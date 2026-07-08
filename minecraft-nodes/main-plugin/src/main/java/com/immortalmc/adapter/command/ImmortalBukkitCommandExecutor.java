package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.targeting.EntityTargetCandidate;
import com.immortalmc.adapter.targeting.EntityTargetSelector;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import net.kyori.adventure.text.Component;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Mob;
import org.bukkit.entity.Player;
import org.bukkit.entity.Villager;
import org.bukkit.event.entity.CreatureSpawnEvent;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public final class ImmortalBukkitCommandExecutor implements CommandExecutor, TabCompleter {
    private static final double MAX_TARGET_DISTANCE = 8.0;
    private static final EntityTargetSelector TARGET_SELECTOR = new EntityTargetSelector(MAX_TARGET_DISTANCE);
    private static final List<String> ROOT_SUBCOMMANDS = List.of("health", "spirit-root", "spirit-root-detector");

    private final ImmortalCommandService commandService;

    public ImmortalBukkitCommandExecutor(ImmortalCommandService commandService) {
        this.commandService = Objects.requireNonNull(commandService, "commandService");
    }

    @Override
    public boolean onCommand(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String label,
            @NotNull String[] args) {
        commandService.execute(args, sourceFor(sender), sender::sendMessage);
        return true;
    }

    @Override
    public @Nullable List<String> onTabComplete(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String label,
            @NotNull String[] args) {
        if (args.length != 1) {
            if (args.length == 2 && "spirit-root-detector".equals(args[0].toLowerCase(Locale.ROOT))) {
                String prefix = args[1].toLowerCase(Locale.ROOT);
                return List.of("create", "list", "remove", "set", "reload").stream()
                        .filter(subcommand -> subcommand.startsWith(prefix))
                        .toList();
            }
            return List.of();
        }
        String prefix = args[0].toLowerCase(Locale.ROOT);
        return ROOT_SUBCOMMANDS.stream()
                .filter(subcommand -> subcommand.startsWith(prefix))
                .toList();
    }

    private static ImmortalCommandSource sourceFor(CommandSender sender) {
        if (sender instanceof Player player) {
            return ImmortalCommandSource.player(
                    player.getUniqueId(),
                    findLookedAtEntity(player),
                    detectorId -> spawnSpiritRootDetector(player, detectorId),
                    binding -> removeEntity(player, binding));
        }
        return ImmortalCommandSource.console();
    }

    private static Optional<EntityInteractionEntity> findLookedAtEntity(Player player) {
        var eyeLocation = player.getEyeLocation();
        List<EntityTargetCandidate> candidates = new ArrayList<>();
        for (Entity entity : player.getNearbyEntities(
                MAX_TARGET_DISTANCE,
                MAX_TARGET_DISTANCE,
                MAX_TARGET_DISTANCE)) {
            if (entity.equals(player) || !player.canSee(entity)) {
                continue;
            }
            candidates.add(new EntityTargetCandidate(
                    new EntityInteractionEntity(
                            new EntityBinding(entity.getWorld().getName(), entity.getUniqueId()),
                            entity.getType().name()),
                    entity.getBoundingBox()));
        }

        return TARGET_SELECTOR.select(
                eyeLocation.toVector(),
                eyeLocation.getDirection(),
                candidates);
    }

    private static EntityInteractionEntity spawnSpiritRootDetector(Player player, String detectorId) {
        Villager villager = player.getWorld().spawn(
                player.getLocation(),
                Villager.class,
                CreatureSpawnEvent.SpawnReason.CUSTOM,
                false,
                spawned -> configureSpawnedDetector(spawned, detectorId));
        return new EntityInteractionEntity(
                new EntityBinding(villager.getWorld().getName(), villager.getUniqueId()),
                villager.getType().name());
    }

    private static boolean removeEntity(Player player, EntityBinding binding) {
        var world = player.getServer().getWorld(binding.worldName());
        if (world == null) {
            return false;
        }
        Entity entity = world.getEntity(binding.entityUuid());
        if (entity == null) {
            return false;
        }
        entity.remove();
        return true;
    }

    private static void configureSpawnedDetector(LivingEntity entity, String detectorId) {
        entity.customName(Component.text("Spirit Root Detector " + detectorId));
        entity.setCustomNameVisible(true);
        entity.setPersistent(true);
        entity.setInvulnerable(true);
        entity.setSilent(true);
        entity.setGravity(false);
        entity.setAI(false);
        if (entity instanceof Mob mob) {
            mob.setAware(false);
        }
        entity.setCollidable(false);
        entity.setRemoveWhenFarAway(false);
    }
}
