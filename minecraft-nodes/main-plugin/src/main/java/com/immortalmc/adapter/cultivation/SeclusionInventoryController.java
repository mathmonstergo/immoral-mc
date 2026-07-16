package com.immortalmc.adapter.cultivation;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SeclusionRequest;
import com.immortalmc.adapter.client.SeclusionSnapshot;
import com.immortalmc.adapter.client.TechniqueSnapshot;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
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
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.plugin.java.JavaPlugin;

public final class SeclusionInventoryController implements Listener, AutoCloseable {
    private static final int CONFIRM_SLOT = 49;
    private static final int CANCEL_SLOT = 45;
    private final JavaPlugin plugin;
    private final GameServiceClient client;
    private final PlayerSessionCache sessions;
    private final CultivationAreaResolver areas;
    private final Consumer<UUID> refresh;

    public SeclusionInventoryController(
            JavaPlugin plugin,
            GameServiceClient client,
            PlayerSessionCache sessions,
            CultivationAreaResolver areas,
            Consumer<UUID> refresh) {
        this.plugin = plugin;
        this.client = client;
        this.sessions = sessions;
        this.areas = areas;
        this.refresh = refresh;
    }

    public void open(Player player) {
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("修为资料尚未载入，请稍后重试。");
            return;
        }
        client.fetchTechniques(session.account().accountId()).whenComplete((techniques, error) ->
                Bukkit.getScheduler().runTask(plugin, () -> {
                    if (!player.isOnline()) {
                        return;
                    }
                    if (error != null) {
                        player.sendMessage("读取功法失败：" + message(error));
                        return;
                    }
                    show(player, techniques);
                }));
    }

    private void show(Player player, List<TechniqueSnapshot> techniques) {
        SeclusionInventoryHolder holder = new SeclusionInventoryHolder(player.getUniqueId(), techniques);
        Inventory inventory = Bukkit.createInventory(holder, 54, Component.text("选择本次闭关功法"));
        holder.attach(inventory);
        for (int slot = 0; slot < Math.min(techniques.size(), 45); slot++) {
            inventory.setItem(slot, item(techniques.get(slot), false));
        }
        inventory.setItem(CANCEL_SLOT, button(Material.BARRIER, "取消"));
        inventory.setItem(CONFIRM_SLOT, button(Material.LIME_CONCRETE, "确认闭关"));
        player.openInventory(inventory);
    }

    @EventHandler
    public void onClick(InventoryClickEvent event) {
        if (!(event.getInventory().getHolder() instanceof SeclusionInventoryHolder holder)) {
            return;
        }
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)
                || !player.getUniqueId().equals(holder.playerId())) {
            return;
        }
        int slot = event.getRawSlot();
        if (slot == CANCEL_SLOT) {
            player.closeInventory();
            return;
        }
        if (slot == CONFIRM_SLOT) {
            confirm(player, holder);
            return;
        }
        if (slot < 0 || slot >= holder.techniques().size()) {
            return;
        }
        TechniqueSnapshot technique = holder.techniques().get(slot);
        if (!holder.selection().toggle(technique.lifeTechniqueId())) {
            player.sendMessage("该功法不可选择：需为 active、未满层，且最多五门同大境界功法。");
            return;
        }
        event.getInventory().setItem(slot, item(technique, holder.selection().selected(technique.lifeTechniqueId())));
    }

    @EventHandler
    public void onClose(InventoryCloseEvent event) {
        // The inventory holder owns all transient selection state.
    }

    private void confirm(Player player, SeclusionInventoryHolder holder) {
        List<UUID> selected;
        try {
            selected = holder.selection().confirmedIds();
        } catch (IllegalStateException error) {
            player.sendMessage("请先选择至少一门功法。");
            return;
        }
        var location = player.getLocation();
        String areaId = areas.resolve(
                        player.getWorld().getName(),
                        location.getX(),
                        location.getY(),
                        location.getZ())
                .orElse(null);
        if (areaId == null) {
            player.sendMessage("你当前不在可闭关区域内。");
            return;
        }
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("修为资料已失效，请重新登录。");
            return;
        }
        player.closeInventory();
        client.startSeclusion(
                        session.account().accountId(),
                        new SeclusionRequest(areaId, selected),
                        UUID.randomUUID())
                .whenComplete((snapshot, error) -> Bukkit.getScheduler().runTask(plugin, () -> {
                    if (error != null) {
                        player.sendMessage("闭关开始失败：" + message(error));
                        return;
                    }
                    player.sendMessage("闭关已开始，预计完成时间：" + snapshot.completesAt());
                    scheduleSettlement(player.getUniqueId(), session.account().accountId(), snapshot);
                    refresh.accept(player.getUniqueId());
                }));
    }

    private void scheduleSettlement(UUID playerId, UUID accountId, SeclusionSnapshot snapshot) {
        scheduleSettlement(
                playerId,
                accountId,
                snapshot.sessionId(),
                CultivationSchedule.delayTicks(Instant.now(), snapshot.completesAt()));
    }

    private void scheduleSettlement(UUID playerId, UUID accountId, UUID sessionId, long delayTicks) {
        Bukkit.getScheduler().runTaskLater(plugin, () -> client.settleSeclusion(
                        accountId,
                        sessionId,
                        UUID.randomUUID())
                .whenComplete((settled, error) -> Bukkit.getScheduler().runTask(plugin, () -> {
                    Player player = Bukkit.getPlayer(playerId);
                    if (error != null) {
                        if (player != null) {
                            player.sendMessage("闭关结算失败：" + message(error));
                        }
                        return;
                    }
                    SeclusionSettlementDecision decision = SeclusionSettlementDecision.from(settled);
                    if (player != null) {
                        player.sendMessage(decision.playerMessage());
                    }
                    refresh.accept(playerId);
                    if (decision.retry()) {
                        scheduleSettlement(
                                playerId,
                                accountId,
                                settled.sessionId(),
                                CultivationSchedule.ACTIVE_SECLUSION_RETRY_TICKS);
                    }
                })), delayTicks);
    }

    private static ItemStack item(TechniqueSnapshot t, boolean selected) {
        ItemStack item = new ItemStack(
                selected ? Material.ENCHANTED_BOOK : Material.BOOK);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(Component.text((selected ? "[已选] " : "") + t.displayName()));
        List<Component> lore = TechniquePresentation.loreLines(t).stream()
                .map(line -> (Component) Component.text(line))
                .toList();
        meta.lore(lore);
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

    private static String message(Throwable error) {
        Throwable cause = error.getCause() == null ? error : error.getCause();
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }

    @Override
    public void close() {
        HandlerList.unregisterAll(this);
    }
}
