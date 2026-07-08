package com.immortalmc.adapter.command;

import java.util.List;
import java.util.Locale;
import java.util.Objects;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

public final class ImmortalBukkitCommandExecutor implements CommandExecutor, TabCompleter {
    private static final List<String> ROOT_SUBCOMMANDS = List.of("health", "spirit-root");

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
            return ImmortalCommandSource.player(player.getUniqueId());
        }
        return ImmortalCommandSource.console();
    }
}
