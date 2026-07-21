package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import com.immortalmc.adapter.client.ItemInstancesSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import java.util.function.Function;
import org.bukkit.entity.Player;

public final class PhysicalItemReconciler implements AutoCloseable {
    private final PhysicalItemGateway gateway;
    private final PlayerSessionCache sessions;
    private final PhysicalInventoryAccess inventory;
    private final Function<UUID, Player> playerLookup;
    private final Consumer<UUID> refreshTrackedQuest;
    private final Consumer<Runnable> mainThread;
    private final AdapterLogger logger;
    private final Map<UUID, UUID> generations = new ConcurrentHashMap<>();

    public PhysicalItemReconciler(
            PhysicalItemGateway gateway,
            PlayerSessionCache sessions,
            PhysicalInventoryAccess inventory,
            Function<UUID, Player> playerLookup,
            Consumer<UUID> refreshTrackedQuest,
            Consumer<Runnable> mainThread,
            AdapterLogger logger) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.inventory = Objects.requireNonNull(inventory, "inventory");
        this.playerLookup = Objects.requireNonNull(playerLookup, "playerLookup");
        this.refreshTrackedQuest = Objects.requireNonNull(refreshTrackedQuest, "refreshTrackedQuest");
        this.mainThread = Objects.requireNonNull(mainThread, "mainThread");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void reconcile(UUID playerId) {
        PlayerLoginResult session = sessions.findByMinecraftUuid(playerId).orElse(null);
        if (session == null) {
            return;
        }
        UUID generation = UUID.randomUUID();
        generations.put(playerId, generation);
        UUID accountId = session.account().accountId();
        gateway.fetchPendingItemDeliveries(accountId)
                .thenCombine(
                        gateway.fetchInventoryItems(accountId),
                        ReconciliationSnapshot::new)
                .whenComplete((snapshot, error) -> mainThread.accept(() -> {
                    if (!generation.equals(generations.get(playerId))) {
                        return;
                    }
                    Player player = playerLookup.apply(playerId);
                    PlayerLoginResult current = sessions.findByMinecraftUuid(playerId).orElse(null);
                    if (player == null
                            || !player.isOnline()
                            || current == null
                            || !current.account().accountId().equals(accountId)) {
                        return;
                    }
                    if (error != null) {
                        logger.warn("physical_item_reconcile_failed player_uuid="
                                + playerId
                                + " reason="
                                + message(error));
                        return;
                    }
                    if (!snapshot.pending().lifeId().equals(current.currentLife().lifeId())
                            || !snapshot.inventory().lifeId().equals(current.currentLife().lifeId())) {
                        logger.warn("physical_item_reconcile_rejected player_uuid="
                                + playerId
                                + " reason=stale_life");
                        return;
                    }
                    try {
                        apply(player, accountId, snapshot);
                    } catch (RuntimeException invalidSnapshot) {
                        logger.warn(
                                "physical_item_reconcile_rejected player_uuid="
                                        + playerId
                                        + " reason=invalid_snapshot",
                                invalidSnapshot);
                    }
                }));
    }

    public void clearPlayer(UUID playerId) {
        generations.remove(playerId);
    }

    private void apply(Player player, UUID accountId, ReconciliationSnapshot snapshot) {
        UUID playerId = player.getUniqueId();
        Map<UUID, ItemInstanceSnapshot> owned = index(snapshot.inventory(), true);
        Map<UUID, ItemInstanceSnapshot> pending = index(snapshot.pending(), false);
        Set<UUID> authoritative = new LinkedHashSet<>(owned.keySet());
        authoritative.addAll(pending.keySet());
        int removed = inventory.removeUnexpected(player.getInventory(), authoritative);
        int restored = 0;
        for (ItemInstanceSnapshot item : owned.values()) {
            if (!inventory.contains(player.getInventory(), item.itemInstanceId())
                    && inventory.add(player.getInventory(), item)) {
                restored++;
            }
        }
        int confirmed = 0;
        for (ItemInstanceSnapshot item : pending.values()) {
            if (!inventory.contains(player.getInventory(), item.itemInstanceId())
                    && !inventory.add(player.getInventory(), item)) {
                continue;
            }
            confirmed++;
            gateway.confirmItemDelivery(accountId, item.itemInstanceId()).whenComplete((ignored, error) -> {
                if (error != null) {
                    logger.warn("physical_item_delivery_confirmation_failed player_uuid="
                            + playerId
                            + " item_instance_id="
                            + item.itemInstanceId()
                            + " reason="
                            + message(error));
                    return;
                }
                try {
                    refreshTrackedQuest.accept(playerId);
                } catch (RuntimeException refreshError) {
                    logger.warn(
                            "physical_item_quest_refresh_failed player_uuid=" + playerId,
                            refreshError);
                }
            });
        }
        if (removed > 0 || restored > 0 || confirmed > 0) {
            logger.info("physical_item_reconcile_applied player_uuid="
                    + playerId
                    + " removed="
                    + removed
                    + " restored="
                    + restored
                    + " confirmations="
                    + confirmed);
        }
    }

    private static Map<UUID, ItemInstanceSnapshot> index(
            ItemInstancesSnapshot snapshot,
            boolean inventoryItems) {
        Map<UUID, ItemInstanceSnapshot> indexed = new LinkedHashMap<>();
        for (ItemInstanceSnapshot item : snapshot.items()) {
            if (inventoryItems ? !item.isOwnedInventory() : !item.isPendingDelivery()) {
                throw new IllegalArgumentException("Item reconciliation response contains an invalid state");
            }
            if (indexed.put(item.itemInstanceId(), item) != null) {
                throw new IllegalArgumentException("Item reconciliation response contains duplicate identities");
            }
        }
        return indexed;
    }

    private static String message(Throwable error) {
        Throwable cause = error.getCause() == null ? error : error.getCause();
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }

    @Override
    public void close() {
        generations.clear();
    }

    private record ReconciliationSnapshot(
            ItemInstancesSnapshot pending,
            ItemInstancesSnapshot inventory) {}
}
