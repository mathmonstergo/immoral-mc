package com.immortalmc.adapter.storage;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.StorageMoveRequest;
import com.immortalmc.adapter.client.StorageMoveSnapshot;
import com.immortalmc.adapter.client.StorageSlotSnapshot;
import com.immortalmc.adapter.client.StorageSnapshot;
import com.immortalmc.adapter.cultivation.CultivationAreaResolver;
import com.immortalmc.adapter.item.PhysicalItemIdentity;
import com.immortalmc.adapter.item.PhysicalInventoryAccess;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import net.kyori.adventure.text.Component;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.plugin.java.JavaPlugin;

public final class RegionalStorageInventoryController implements Listener, AutoCloseable {
    private static final int INVENTORY_SIZE = 54;
    private static final int PREVIOUS_PAGE_SLOT = 45;
    private static final int REFRESH_SLOT = 48;
    private static final int STATUS_SLOT = 49;
    private static final int CLOSE_SLOT = 50;
    private static final int NEXT_PAGE_SLOT = 53;

    private final JavaPlugin plugin;
    private final RegionalStorageGateway gateway;
    private final PlayerSessionCache sessions;
    private final RegionalStorageAccessPolicy accessPolicy;
    private final CultivationAreaResolver areas;
    private final PhysicalInventoryAccess physicalInventory;
    private final Consumer<UUID> reconcile;
    private final Consumer<Runnable> mainThread;
    private final AdapterLogger logger;
    private final Map<UUID, UUID> generations = new ConcurrentHashMap<>();
    private final Map<UUID, RegionalStorageInventoryHolder> openStorages = new ConcurrentHashMap<>();

    public RegionalStorageInventoryController(
            JavaPlugin plugin,
            RegionalStorageGateway gateway,
            PlayerSessionCache sessions,
            CultivationAreaResolver areas,
            PhysicalInventoryAccess physicalInventory,
            Consumer<UUID> reconcile,
            Consumer<Runnable> mainThread,
            AdapterLogger logger) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
        this.gateway = Objects.requireNonNull(gateway, "gateway");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.accessPolicy = new RegionalStorageAccessPolicy(sessions);
        this.areas = Objects.requireNonNull(areas, "areas");
        this.physicalInventory = Objects.requireNonNull(physicalInventory, "physicalInventory");
        this.reconcile = Objects.requireNonNull(reconcile, "reconcile");
        this.mainThread = Objects.requireNonNull(mainThread, "mainThread");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void open(Player player) {
        Objects.requireNonNull(player, "player");
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("§c角色资料尚未加载，请稍后重试。");
            return;
        }
        String areaId = currentArea(player);
        if (areaId == null) {
            player.sendMessage("§e你当前不在已配置仓库的地区内。");
            return;
        }
        UUID generation = UUID.randomUUID();
        generations.put(player.getUniqueId(), generation);
        reconcile.accept(player.getUniqueId());
        gateway.fetchStorage(session.account().accountId(), areaId, 1)
                .whenComplete((snapshot, error) -> mainThread.accept(() -> {
                    if (!generation.equals(generations.get(player.getUniqueId()))
                            || !player.isOnline()) {
                        return;
                    }
                    if (error != null) {
                        player.sendMessage("§c读取地区仓库失败：" + message(error));
                        logFailure("regional_storage_open_failed", player, areaId, error);
                        return;
                    }
                    if (!sameSession(player.getUniqueId(), session)
                            || !areaId.equals(currentArea(player))) {
                        player.sendMessage("§e你已离开该地区，仓库未打开。");
                        return;
                    }
                    if (!player.hasPermission(snapshot.permission())) {
                        player.sendMessage("§c你没有使用该地区仓库的权限。");
                        return;
                    }
                    show(player, session, areaId, snapshot);
                }));
    }

    @EventHandler
    public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder()
                instanceof RegionalStorageInventoryHolder holder)) {
            return;
        }
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)
                || !player.getUniqueId().equals(holder.playerId())
                || !isCurrent(holder)) {
            return;
        }
        if (holder.busy()) {
            player.sendMessage("§e仓库正在同步，请稍候。");
            return;
        }
        int rawSlot = event.getRawSlot();
        if (rawSlot < 0) {
            return;
        }
        if (rawSlot < INVENTORY_SIZE) {
            handleTopClick(player, holder, rawSlot, event.isRightClick());
            return;
        }
        depositClickedItem(player, holder, event.getCurrentItem());
    }

    @EventHandler
    public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder()
                instanceof RegionalStorageInventoryHolder) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onClose(InventoryCloseEvent event) {
        if (!(event.getInventory().getHolder() instanceof RegionalStorageInventoryHolder holder)) {
            return;
        }
        openStorages.remove(holder.playerId(), holder);
        generations.remove(holder.playerId());
        reconcile.accept(holder.playerId());
    }

    @EventHandler(ignoreCancelled = true)
    public void onMove(PlayerMoveEvent event) {
        RegionalStorageInventoryHolder holder = openStorages.get(event.getPlayer().getUniqueId());
        if (holder == null || event.getTo() == null || sameBlock(event)) {
            return;
        }
        Player player = event.getPlayer();
        String destinationArea = areas.resolve(
                        event.getTo().getWorld().getName(),
                        event.getTo().getX(),
                        event.getTo().getY(),
                        event.getTo().getZ())
                .orElse(null);
        if (!accessPolicy.allows(player, holder, destinationArea)) {
            player.sendMessage("§e你已离开该地区或仓库权限已失效。");
            player.closeInventory();
        }
    }

    public void clearPlayer(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        generations.remove(playerId);
        RegionalStorageInventoryHolder holder = openStorages.remove(playerId);
        Player player = Bukkit.getPlayer(playerId);
        if (holder != null
                && player != null
                && player.getOpenInventory().getTopInventory().getHolder() == holder) {
            player.closeInventory();
        }
    }

    private void show(
            Player player,
            PlayerLoginResult session,
            String areaId,
            StorageSnapshot snapshot) {
        RegionalStorageInventoryHolder previous = openStorages.remove(player.getUniqueId());
        if (previous != null) {
            player.closeInventory();
        }
        RegionalStorageInventoryHolder holder = new RegionalStorageInventoryHolder(
                player.getUniqueId(),
                session.account().accountId(),
                session.currentLife().lifeId(),
                areaId,
                snapshot);
        Inventory inventory = Bukkit.createInventory(
                holder,
                INVENTORY_SIZE,
                Component.text("地区仓库 · " + areaId));
        holder.attach(inventory);
        openStorages.put(player.getUniqueId(), holder);
        render(holder);
        player.openInventory(inventory);
    }

    private void handleTopClick(
            Player player,
            RegionalStorageInventoryHolder holder,
            int slot,
            boolean rightClick) {
        if (slot >= holder.snapshot().itemSlotsPerPage()) {
            handleControl(player, holder, slot);
            return;
        }
        Integer selected = holder.selectedSlot();
        if (selected != null) {
            if (selected == slot) {
                holder.select(null);
                render(holder);
                return;
            }
            moveWithinPage(player, holder, selected, slot);
            return;
        }
        StorageSlotSnapshot stored = holder.snapshot().slot(slot);
        if (stored == null) {
            return;
        }
        if (rightClick) {
            holder.select(slot);
            render(holder);
            return;
        }
        withdraw(player, holder, stored);
    }

    private void handleControl(Player player, RegionalStorageInventoryHolder holder, int slot) {
        StorageSnapshot snapshot = holder.snapshot();
        if (slot == CLOSE_SLOT) {
            player.closeInventory();
            return;
        }
        if (slot == REFRESH_SLOT) {
            fetchPage(player, holder, snapshot.page());
            return;
        }
        if (slot == PREVIOUS_PAGE_SLOT && snapshot.page() > 1) {
            fetchPage(player, holder, snapshot.page() - 1);
            return;
        }
        if (slot == NEXT_PAGE_SLOT && snapshot.page() < snapshot.pageCount()) {
            fetchPage(player, holder, snapshot.page() + 1);
        }
    }

    private void depositClickedItem(
            Player player,
            RegionalStorageInventoryHolder holder,
            ItemStack clicked) {
        PhysicalItemIdentity identity;
        try {
            identity = physicalInventory.identity(clicked).orElse(null);
        } catch (RuntimeException error) {
            player.sendMessage("§c该实体物品数据无效，无法存入仓库。");
            reconcile.accept(player.getUniqueId());
            return;
        }
        if (identity == null) {
            return;
        }
        int destination = firstEmptySlot(holder.snapshot());
        if (destination < 0) {
            player.sendMessage("§e当前仓库页没有空槽位。");
            return;
        }
        mutate(
                player,
                holder,
                StorageMoveRequest.deposit(
                        identity.itemInstanceId(),
                        holder.snapshot().revision(),
                        holder.snapshot().page(),
                        destination));
    }

    private void withdraw(
            Player player,
            RegionalStorageInventoryHolder holder,
            StorageSlotSnapshot stored) {
        if (!physicalInventory.contains(player.getInventory(), stored.item().itemInstanceId())
                && player.getInventory().firstEmpty() < 0) {
            player.sendMessage("§e背包已满，无法取出该物品。");
            return;
        }
        mutate(
                player,
                holder,
                StorageMoveRequest.withdraw(
                        stored.item().itemInstanceId(),
                        holder.snapshot().revision(),
                        holder.snapshot().page(),
                        stored.slot()));
    }

    private void moveWithinPage(
            Player player,
            RegionalStorageInventoryHolder holder,
            int sourceSlot,
            int destinationSlot) {
        StorageSlotSnapshot source = holder.snapshot().slot(sourceSlot);
        if (source == null) {
            holder.select(null);
            render(holder);
            return;
        }
        mutate(
                player,
                holder,
                StorageMoveRequest.move(
                        source.item().itemInstanceId(),
                        holder.snapshot().revision(),
                        holder.snapshot().page(),
                        sourceSlot,
                        destinationSlot));
    }

    private void mutate(
            Player player,
            RegionalStorageInventoryHolder holder,
            StorageMoveRequest request) {
        if (!validateAccess(player, holder) || !holder.beginOperation()) {
            return;
        }
        render(holder);
        UUID operationId = UUID.randomUUID();
        gateway.moveStorage(holder.accountId(), holder.areaId(), request, operationId)
                .whenComplete((result, error) -> mainThread.accept(() ->
                        finishMutation(player, holder, operationId, result, error)));
    }

    private void finishMutation(
            Player player,
            RegionalStorageInventoryHolder holder,
            UUID operationId,
            StorageMoveSnapshot result,
            Throwable error) {
        holder.finishOperation();
        reconcile.accept(holder.playerId());
        if (!isCurrent(holder) || !player.isOnline()) {
            return;
        }
        if (error != null
                || result == null
                || !operationId.equals(result.operationId())) {
            player.sendMessage("§e仓库操作结果未确认，正在读取权威快照。");
            if (error != null) {
                logFailure("regional_storage_move_failed", player, holder.areaId(), error);
            }
            fetchPage(player, holder, holder.snapshot().page());
            return;
        }
        if (!validateAccess(player, holder)) {
            return;
        }
        holder.update(result.snapshot());
        render(holder);
    }

    private void fetchPage(
            Player player,
            RegionalStorageInventoryHolder holder,
            int page) {
        if (!validateAccess(player, holder) || !holder.beginOperation()) {
            return;
        }
        render(holder);
        gateway.fetchStorage(holder.accountId(), holder.areaId(), page)
                .whenComplete((snapshot, error) -> mainThread.accept(() -> {
                    holder.finishOperation();
                    if (!isCurrent(holder) || !player.isOnline()) {
                        return;
                    }
                    if (error != null) {
                        player.sendMessage("§c刷新地区仓库失败：" + message(error));
                        logFailure("regional_storage_refresh_failed", player, holder.areaId(), error);
                        render(holder);
                        return;
                    }
                    if (!validateAccess(player, holder)) {
                        return;
                    }
                    holder.update(snapshot);
                    render(holder);
                }));
    }

    private boolean validateAccess(Player player, RegionalStorageInventoryHolder holder) {
        if (!isCurrent(holder)
                || !accessPolicy.allows(player, holder, currentArea(player))) {
            player.sendMessage("§e你已离开该地区或仓库权限已失效。");
            player.closeInventory();
            return false;
        }
        return true;
    }

    private boolean isCurrent(RegionalStorageInventoryHolder holder) {
        return openStorages.get(holder.playerId()) == holder;
    }

    private boolean sameSession(UUID playerId, PlayerLoginResult expected) {
        PlayerLoginResult current = sessions.findByMinecraftUuid(playerId).orElse(null);
        return current != null
                && current.account().accountId().equals(expected.account().accountId())
                && current.currentLife().lifeId().equals(expected.currentLife().lifeId());
    }

    private String currentArea(Player player) {
        var location = player.getLocation();
        return areas.resolve(
                        player.getWorld().getName(),
                        location.getX(),
                        location.getY(),
                        location.getZ())
                .orElse(null);
    }

    private void render(RegionalStorageInventoryHolder holder) {
        Inventory inventory = holder.getInventory();
        inventory.clear();
        StorageSnapshot snapshot = holder.snapshot();
        for (StorageSlotSnapshot stored : snapshot.slots()) {
            ItemStack item = physicalInventory.create(stored.item());
            if (Objects.equals(holder.selectedSlot(), stored.slot())) {
                ItemMeta meta = item.getItemMeta();
                meta.displayName(Component.text("[移动] ").append(meta.displayName()));
                item.setItemMeta(meta);
            }
            inventory.setItem(stored.slot(), item);
        }
        inventory.setItem(
                PREVIOUS_PAGE_SLOT,
                button(
                        snapshot.page() > 1 ? Material.ARROW : Material.GRAY_DYE,
                        "上一页"));
        inventory.setItem(REFRESH_SLOT, button(Material.CLOCK, "刷新"));
        inventory.setItem(
                STATUS_SLOT,
                statusButton(holder));
        inventory.setItem(CLOSE_SLOT, button(Material.BARRIER, "关闭"));
        inventory.setItem(
                NEXT_PAGE_SLOT,
                button(
                        snapshot.page() < snapshot.pageCount() ? Material.ARROW : Material.GRAY_DYE,
                        "下一页"));
        for (int slot : new int[] {46, 47, 51, 52}) {
            inventory.setItem(slot, button(Material.GRAY_STAINED_GLASS_PANE, " "));
        }
    }

    private static ItemStack statusButton(RegionalStorageInventoryHolder holder) {
        StorageSnapshot snapshot = holder.snapshot();
        ItemStack item = new ItemStack(holder.busy() ? Material.YELLOW_STAINED_GLASS_PANE : Material.CHEST);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(Component.text(holder.busy() ? "同步中" : "地区仓库"));
        meta.lore(java.util.List.of(
                Component.text("地区：" + snapshot.areaId()),
                Component.text("页码：" + snapshot.page() + "/" + snapshot.pageCount()),
                Component.text("修订：" + snapshot.revision())));
        item.setItemMeta(meta);
        return item;
    }

    private static ItemStack button(Material material, String name) {
        ItemStack item = new ItemStack(material);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(Component.text(name));
        item.setItemMeta(meta);
        return item;
    }

    private static int firstEmptySlot(StorageSnapshot snapshot) {
        for (int slot = 0; slot < snapshot.itemSlotsPerPage(); slot++) {
            if (snapshot.slot(slot) == null) {
                return slot;
            }
        }
        return -1;
    }

    private void logFailure(String event, Player player, String areaId, Throwable error) {
        logger.warn(event
                + " minecraft_uuid=" + player.getUniqueId()
                + " area_id=" + areaId
                + " reason=" + message(error));
    }

    private static String message(Throwable error) {
        Throwable cause = error.getCause() == null ? error : error.getCause();
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }

    private static boolean sameBlock(PlayerMoveEvent event) {
        return event.getFrom().getWorld().equals(event.getTo().getWorld())
                && event.getFrom().getBlockX() == event.getTo().getBlockX()
                && event.getFrom().getBlockY() == event.getTo().getBlockY()
                && event.getFrom().getBlockZ() == event.getTo().getBlockZ();
    }

    @Override
    public void close() {
        generations.clear();
        openStorages.clear();
        HandlerList.unregisterAll(this);
    }
}
