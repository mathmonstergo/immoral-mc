package com.immortalmc.adapter.command;

import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.citizens.CitizensNpcSelector;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.targeting.EntityTargetCandidate;
import com.immortalmc.adapter.targeting.EntityTargetSelector;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Consumer;
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
    private static final String ADMIN_PERMISSION = "immortalmc.command";
    private static final String CULTIVATION_PERMISSION = "immortalmc.cultivation";
    private static final String STORAGE_PERMISSION = "immortalmc.storage";
    private static final EntityTargetSelector TARGET_SELECTOR = new EntityTargetSelector(MAX_TARGET_DISTANCE);
    private static final List<String> ROOT_SUBCOMMANDS = List.of(
            "health",
            "spirit-root",
            "spirit-root-detector",
            "npc-dialogue",
            "quest",
            "seclusion",
            "breakthrough",
            "cultivation",
            "storage");

    private final ImmortalCommandService commandService;
    private final CitizensNpcResolver citizensNpcResolver;
    private final CitizensNpcSelector citizensNpcSelector;
    private final QuestProviderCatalogCache questProviderCatalog;
    private final CommandBranch cultivationCommands;
    private final Consumer<Player> storageOpener;

    public ImmortalBukkitCommandExecutor(
            ImmortalCommandService commandService,
            CitizensNpcResolver citizensNpcResolver,
            CitizensNpcSelector citizensNpcSelector,
            QuestProviderCatalogCache questProviderCatalog,
            CommandBranch cultivationCommands,
            Consumer<Player> storageOpener) {
        this.commandService = Objects.requireNonNull(commandService, "commandService");
        this.citizensNpcResolver = Objects.requireNonNull(citizensNpcResolver, "citizensNpcResolver");
        this.citizensNpcSelector = Objects.requireNonNull(citizensNpcSelector, "citizensNpcSelector");
        this.questProviderCatalog = Objects.requireNonNull(questProviderCatalog, "questProviderCatalog");
        this.cultivationCommands = Objects.requireNonNull(cultivationCommands, "cultivationCommands");
        this.storageOpener = Objects.requireNonNull(storageOpener, "storageOpener");
    }

    @Override
    public boolean onCommand(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String label,
            @NotNull String[] args) {
        if (args.length > 0 && "storage".equalsIgnoreCase(args[0])) {
            if (!(sender instanceof Player player)) {
                sender.sendMessage("地区仓库只能由玩家使用。");
                return true;
            }
            if (!sender.hasPermission(STORAGE_PERMISSION)) {
                sender.sendMessage("你没有使用地区仓库的权限。");
                return true;
            }
            storageOpener.accept(player);
            return true;
        }
        if (isPlayerCultivationCommand(args)) {
            if (!sender.hasPermission(CULTIVATION_PERMISSION)) {
                sender.sendMessage("你没有使用修炼命令的权限。");
                return true;
            }
        } else if (!sender.hasPermission(ADMIN_PERMISSION)) {
            sender.sendMessage("你没有使用管理命令的权限。");
            return true;
        }
        if (!cultivationCommands.handle(sender, args)) {
            commandService.execute(args, sourceFor(sender), sender::sendMessage);
        }
        return true;
    }

    private static boolean isPlayerCultivationCommand(String[] args) {
        if (args.length == 0) {
            return false;
        }
        String subcommand = args[0].toLowerCase(Locale.ROOT);
        return "seclusion".equals(subcommand) || "breakthrough".equals(subcommand);
    }

    @Override
    public @Nullable List<String> onTabComplete(
            @NotNull CommandSender sender,
            @NotNull Command command,
            @NotNull String label,
            @NotNull String[] args) {
        return complete(args);
    }

    List<String> complete(String[] args) {
        if (args.length != 1) {
            if (args.length == 2 && "spirit-root-detector".equals(args[0].toLowerCase(Locale.ROOT))) {
                String prefix = args[1].toLowerCase(Locale.ROOT);
                return List.of("create", "list", "remove", "set", "reload").stream()
                        .filter(subcommand -> subcommand.startsWith(prefix))
                        .toList();
            }
            if (args.length == 2 && "npc-dialogue".equals(args[0].toLowerCase(Locale.ROOT))) {
                String prefix = args[1].toLowerCase(Locale.ROOT);
                return List.of("set", "list", "remove", "reload").stream()
                        .filter(subcommand -> subcommand.startsWith(prefix))
                        .toList();
            }
            if (args.length == 2 && "quest".equals(args[0].toLowerCase(Locale.ROOT))) {
                String prefix = args[1].toLowerCase(Locale.ROOT);
                return List.of("templates", "bind", "info", "list", "unbind", "reload").stream()
                        .filter(subcommand -> subcommand.startsWith(prefix))
                        .toList();
            }
            if (args.length == 3
                    && "quest".equals(args[0].toLowerCase(Locale.ROOT))
                    && "bind".equals(args[1].toLowerCase(Locale.ROOT))) {
                String prefix = args[2].toLowerCase(Locale.ROOT);
                return questProviderCatalog.providerIds().stream()
                        .filter(providerId -> providerId.toLowerCase(Locale.ROOT).startsWith(prefix))
                        .toList();
            }
            return List.of();
        }
        String prefix = args[0].toLowerCase(Locale.ROOT);
        return ROOT_SUBCOMMANDS.stream()
                .filter(subcommand -> subcommand.startsWith(prefix))
                .toList();
    }

    private ImmortalCommandSource sourceFor(CommandSender sender) {
        if (sender instanceof Player player) {
            Optional<EntityInteractionEntity> lookedAtEntity = findLookedAtEntity(player);
            return ImmortalCommandSource.player(
                    player.getUniqueId(),
                    lookedAtEntity,
                    lookedAtEntity.flatMap(entity -> resolveCitizensNpcUuid(player, entity)),
                    detectorId -> spawnSpiritRootDetector(player, detectorId),
                    binding -> removeEntity(player, binding),
                    citizensNpcSelector.selectedNpc(player));
        }
        return ImmortalCommandSource.console();
    }

    private Optional<UUID> resolveCitizensNpcUuid(Player player, EntityInteractionEntity target) {
        var world = player.getServer().getWorld(target.binding().worldName());
        if (world == null) {
            return Optional.empty();
        }
        Entity entity = world.getEntity(target.binding().entityUuid());
        return entity == null ? Optional.empty() : citizensNpcResolver.persistentNpcUuid(entity);
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

    @FunctionalInterface
    public interface CommandBranch {
        boolean handle(CommandSender sender, String[] args);
    }
}
