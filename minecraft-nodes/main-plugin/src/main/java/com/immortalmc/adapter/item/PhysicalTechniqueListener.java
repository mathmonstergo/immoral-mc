package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.LearnTechniqueSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.ItemStack;

/** Converts an authoritative technique manual into a layer-zero learned technique. */
public final class PhysicalTechniqueListener implements Listener, AutoCloseable {
    private final TechniqueLearningGateway gateway;
    private final PlayerSessionCache sessions;
    private final PhysicalInventoryAccess inventory;
    private final Consumer<UUID> reconcile;
    private final Consumer<UUID> refresh;
    private final Consumer<Runnable> mainThread;
    private final AdapterLogger logger;
    private final Map<UUID, UUID> inFlight = new ConcurrentHashMap<>();

    public PhysicalTechniqueListener(
            TechniqueLearningGateway gateway,
            PlayerSessionCache sessions,
            PhysicalInventoryAccess inventory,
            Consumer<UUID> reconcile,
            Consumer<UUID> refresh,
            Consumer<Runnable> mainThread,
            AdapterLogger logger) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.inventory = Objects.requireNonNull(inventory, "inventory");
        this.reconcile = Objects.requireNonNull(reconcile, "reconcile");
        this.refresh = Objects.requireNonNull(refresh, "refresh");
        this.mainThread = Objects.requireNonNull(mainThread, "mainThread");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onInteract(PlayerInteractEvent event) {
        if (event.getAction() != Action.RIGHT_CLICK_AIR
                && event.getAction() != Action.RIGHT_CLICK_BLOCK) {
            return;
        }
        if (useManual(event.getPlayer(), event.getItem())) {
            event.setCancelled(true);
        }
    }

    boolean useManual(Player player, ItemStack item) {
        PhysicalItemIdentity identity;
        try {
            identity = inventory.identity(item).orElse(null);
        } catch (RuntimeException error) {
            player.sendMessage("§c该实体物品数据无效，已阻止使用。");
            logger.warn("physical_item_rejected reason=invalid_metadata", error);
            return true;
        }
        if (identity == null || !identity.isTechniqueManual()) {
            return false;
        }
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("§c角色资料尚未加载，请稍后再试。");
            return true;
        }
        UUID itemInstanceId = identity.itemInstanceId();
        UUID previous = inFlight.putIfAbsent(player.getUniqueId(), itemInstanceId);
        if (previous != null) {
            player.sendMessage("§e正在研读秘籍，请稍候。");
            return true;
        }
        UUID operationId = UUID.nameUUIDFromBytes(
                ("immortalmc:technique-learn:" + itemInstanceId)
                        .getBytes(StandardCharsets.UTF_8));
        gateway.learnTechnique(session.account().accountId(), itemInstanceId, operationId)
                .whenComplete((result, error) -> mainThread.accept(() ->
                        finish(player, session, itemInstanceId, operationId, result, error)));
        return true;
    }

    private void finish(
            Player player,
            PlayerLoginResult session,
            UUID itemInstanceId,
            UUID operationId,
            LearnTechniqueSnapshot result,
            Throwable error) {
        inFlight.remove(player.getUniqueId(), itemInstanceId);
        reconcile.accept(player.getUniqueId());
        if (error != null
                || result == null
                || !operationId.equals(result.operationId())
                || !itemInstanceId.equals(result.itemInstanceId())) {
            if (player.isOnline()) {
                player.sendMessage("§c秘籍研读失败，请稍后重试。");
            }
            logger.warn(
                    "technique_learn_failed minecraft_uuid=" + player.getUniqueId()
                            + " account_id=" + session.account().accountId()
                            + " item_instance_id=" + itemInstanceId
                            + " reason=" + message(error));
            return;
        }
        if (!player.isOnline()) {
            return;
        }
        PlayerLoginResult current = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (current == null
                || !current.account().accountId().equals(session.account().accountId())
                || !current.currentLife().lifeId().equals(session.currentLife().lifeId())) {
            return;
        }
        player.sendMessage("§a已学会功法：§f" + result.displayName() + " §7（第 0 层）");
        refresh.accept(player.getUniqueId());
    }

    public void clearPlayer(UUID playerId) {
        inFlight.remove(Objects.requireNonNull(playerId, "playerId"));
    }

    @Override
    public void close() {
        inFlight.clear();
    }

    private static String message(Throwable error) {
        if (error == null) {
            return "invalid_response";
        }
        Throwable cause = error.getCause() == null ? error : error.getCause();
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }
}
