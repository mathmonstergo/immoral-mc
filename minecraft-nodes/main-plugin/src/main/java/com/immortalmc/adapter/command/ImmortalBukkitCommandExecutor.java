package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Optional;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public final class ImmortalBukkitCommandExecutor implements CommandExecutor, TabCompleter {
    private static final double MAX_TARGET_DISTANCE = 8.0;
    private static final double MIN_TARGET_DOT = 0.95;
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
            return List.of();
        }
        String prefix = args[0].toLowerCase(Locale.ROOT);
        return ROOT_SUBCOMMANDS.stream()
                .filter(subcommand -> subcommand.startsWith(prefix))
                .toList();
    }

    private static ImmortalCommandSource sourceFor(CommandSender sender) {
        if (sender instanceof Player player) {
            Optional<EntityBinding> lookedAtEntity = findLookedAtEntity(player);
            if (lookedAtEntity.isPresent()) {
                return ImmortalCommandSource.player(player.getUniqueId(), lookedAtEntity.orElseThrow());
            }
            return ImmortalCommandSource.player(player.getUniqueId());
        }
        return ImmortalCommandSource.console();
    }

    private static Optional<EntityBinding> findLookedAtEntity(Player player) {
        Entity bestEntity = null;
        double bestDistance = Double.MAX_VALUE;
        var eyeLocation = player.getEyeLocation();
        var eyeVector = eyeLocation.toVector();
        var direction = eyeLocation.getDirection().normalize();

        for (Entity entity : player.getNearbyEntities(MAX_TARGET_DISTANCE, MAX_TARGET_DISTANCE, MAX_TARGET_DISTANCE)) {
            var toEntity = entity.getLocation().toVector().subtract(eyeVector);
            double distance = toEntity.length();
            if (distance <= 0.0 || distance > MAX_TARGET_DISTANCE) {
                continue;
            }
            double dot = direction.dot(toEntity.normalize());
            if (dot < MIN_TARGET_DOT || distance >= bestDistance) {
                continue;
            }
            bestEntity = entity;
            bestDistance = distance;
        }

        if (bestEntity == null) {
            return Optional.empty();
        }
        return Optional.of(new EntityBinding(bestEntity.getWorld().getName(), bestEntity.getUniqueId()));
    }
}
