package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.BreakthroughRequest;
import com.immortalmc.adapter.client.BreakthroughSnapshot;
import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.ItemAdjustmentRequest;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.time.Instant;
import java.util.UUID;
import java.util.function.Consumer;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;

public final class CultivationCommandRunner {
    private final JavaPlugin plugin;
    private final GameServiceClient client;
    private final PlayerSessionCache sessions;
    private final SeclusionInventoryController seclusion;
    private final Consumer<UUID> refresh;

    public CultivationCommandRunner(
            JavaPlugin plugin,
            GameServiceClient client,
            PlayerSessionCache sessions,
            SeclusionInventoryController seclusion,
            Consumer<UUID> refresh) {
        this.plugin = plugin;
        this.client = client;
        this.sessions = sessions;
        this.seclusion = seclusion;
        this.refresh = refresh;
    }

    public boolean handle(CommandSender sender, String[] args) {
        if (args.length == 1 && "seclusion".equalsIgnoreCase(args[0])) {
            if (!(sender instanceof Player player)) {
                sender.sendMessage("该命令只能由玩家执行。");
            } else {
                seclusion.open(player);
            }
            return true;
        }
        if (args.length == 2 && "breakthrough".equalsIgnoreCase(args[0])) {
            if (!(sender instanceof Player player)) {
                sender.sendMessage("该命令只能由玩家执行。");
                return true;
            }
            int count;
            try {
                count = Integer.parseInt(args[1]);
            } catch (NumberFormatException error) {
                sender.sendMessage("pill-count 必须是 1-10 的整数。");
                return true;
            }
            breakthrough(player, count);
            return true;
        }
        if (args.length == 5
                && "cultivation".equalsIgnoreCase(args[0])
                && "grant-item".equalsIgnoreCase(args[1])) {
            grant(sender, args[2], args[3], args[4]);
            return true;
        }
        return false;
    }

    private void breakthrough(Player player, int count) {
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("修为资料尚未载入。");
            return;
        }
        try {
            client.startBreakthrough(session.account().accountId(), new BreakthroughRequest(count), UUID.randomUUID())
                    .whenComplete((snapshot, error) -> sync(() -> {
                        if (error != null) {
                            player.sendMessage("突破开始失败：" + message(error));
                            return;
                        }
                        player.sendMessage("突破已开始，预计完成时间：" + snapshot.completesAt());
                        refresh.accept(player.getUniqueId());
                        scheduleBreakthrough(player.getUniqueId(), session.account().accountId(), snapshot);
                    }));
        } catch (IllegalArgumentException error) {
            player.sendMessage(error.getMessage());
        }
    }

    private void scheduleBreakthrough(UUID playerId, UUID accountId, BreakthroughSnapshot snapshot) {
        long ticks = CultivationSchedule.delayTicks(Instant.now(), snapshot.completesAt());
        Bukkit.getScheduler().runTaskLater(plugin, () -> client.fetchBreakthrough(accountId, snapshot.sessionId())
                .thenCompose(status -> client.settleBreakthrough(accountId, status.sessionId(), UUID.randomUUID()))
                .whenComplete((settled, error) -> sync(() -> {
                    Player player = Bukkit.getPlayer(playerId);
                    if (player != null) {
                        player.sendMessage(error == null
                                ? "突破结算：" + settled.outcome()
                                : "突破结算失败：" + message(error));
                    }
                    if (error == null) {
                        refresh.accept(playerId);
                    }
                })), ticks);
    }

    private void grant(CommandSender sender, String playerName, String itemCode, String countText) {
        if (!sender.isOp()) {
            sender.sendMessage("该命令仅限管理员。");
            return;
        }
        Player target = Bukkit.getPlayerExact(playerName);
        if (target == null) {
            sender.sendMessage("玩家不在线。");
            return;
        }
        PlayerLoginResult session = sessions.findByMinecraftUuid(target.getUniqueId()).orElse(null);
        if (session == null) {
            sender.sendMessage("目标玩家资料尚未载入。");
            return;
        }
        long count;
        try {
            count = Long.parseLong(countText);
        } catch (NumberFormatException error) {
            sender.sendMessage("count 必须是正整数。");
            return;
        }
        try {
            client.adjustItem(
                            session.account().accountId(),
                            new ItemAdjustmentRequest(itemCode, count),
                            UUID.randomUUID())
                    .whenComplete((result, error) -> sync(() -> {
                        sender.sendMessage(error == null
                                ? "已发放 " + result.itemCode() + " x" + result.deltaQuantity() + "，余额 " + result.balanceAfter()
                                : "发放失败：" + message(error));
                        if (error == null) {
                            refresh.accept(target.getUniqueId());
                        }
                    }));
        } catch (IllegalArgumentException error) {
            sender.sendMessage(error.getMessage());
        }
    }

    private void sync(Runnable task) {
        Bukkit.getScheduler().runTask(plugin, task);
    }

    private static String message(Throwable error) {
        Throwable cause = error.getCause() == null ? error : error.getCause();
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }
}
