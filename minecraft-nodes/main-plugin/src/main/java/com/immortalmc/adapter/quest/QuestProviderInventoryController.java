package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.QuestRewardPreview;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiConsumer;
import java.util.function.Consumer;
import java.util.function.Function;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextDecoration;
import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

/** Owns the read-only six-row quest-provider list/detail inventory lifecycle. */
public final class QuestProviderInventoryController
        implements Listener, QuestProviderGuiOpener, AutoCloseable {
    public static final int INVENTORY_SIZE = 54;
    public static final int CONTENT_SIZE = 45;
    static final int BACK_SLOT = 45;
    static final int PREVIOUS_SLOT = 47;
    static final int REFRESH_SLOT = 49;
    static final int CLOSE_SLOT = 50;
    static final int NEXT_SLOT = 51;
    static final int PRIMARY_SLOT = 53;
    private static final int DETAIL_HEADER_SLOT = 4;
    private static final int DETAIL_DIVIDER_START = 9;
    private static final int DETAIL_DIVIDER_END = 17;
    private static final int DETAIL_OBJECTIVE_START = 18;
    private static final int DETAIL_REWARD_SLOT = 40;

    private final PlayerSessionCache sessions;
    private final QuestInteractionService quests;
    private final ProviderBindingValidator bindings;
    private final Function<Player, List<UUID>> inventoryItemIds;
    private final BiConsumer<UUID, QuestInteractionState> statePublisher;
    private final Consumer<UUID> reconcileItems;
    private final Consumer<UUID> refreshCultivation;
    private final Consumer<Runnable> mainThread;
    private final Function<UUID, Player> playerLookup;
    private final InventoryFactory inventoryFactory;
    private final MenuItemFactory itemFactory;
    private final AdapterLogger logger;
    private final Map<UUID, UUID> generations = new ConcurrentHashMap<>();
    private final Map<UUID, QuestProviderInventoryHolder> openMenus = new ConcurrentHashMap<>();

    public QuestProviderInventoryController(
            PlayerSessionCache sessions,
            QuestInteractionService quests,
            ProviderBindingValidator bindings,
            Function<Player, List<UUID>> inventoryItemIds,
            BiConsumer<UUID, QuestInteractionState> statePublisher,
            Consumer<UUID> reconcileItems,
            Consumer<UUID> refreshCultivation,
            Consumer<Runnable> mainThread,
            AdapterLogger logger) {
        this(
                sessions,
                quests,
                bindings,
                inventoryItemIds,
                statePublisher,
                reconcileItems,
                refreshCultivation,
                mainThread,
                Bukkit::getPlayer,
                (holder, size, title) -> Bukkit.createInventory(holder, size, title),
                QuestProviderInventoryController::createItem,
                logger);
    }

    QuestProviderInventoryController(
            PlayerSessionCache sessions,
            QuestInteractionService quests,
            ProviderBindingValidator bindings,
            Function<Player, List<UUID>> inventoryItemIds,
            BiConsumer<UUID, QuestInteractionState> statePublisher,
            Consumer<UUID> reconcileItems,
            Consumer<UUID> refreshCultivation,
            Consumer<Runnable> mainThread,
            Function<UUID, Player> playerLookup,
            InventoryFactory inventoryFactory,
            MenuItemFactory itemFactory,
            AdapterLogger logger) {
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.quests = Objects.requireNonNull(quests, "quests");
        this.bindings = Objects.requireNonNull(bindings, "bindings");
        this.inventoryItemIds = Objects.requireNonNull(inventoryItemIds, "inventoryItemIds");
        this.statePublisher = Objects.requireNonNull(statePublisher, "statePublisher");
        this.reconcileItems = Objects.requireNonNull(reconcileItems, "reconcileItems");
        this.refreshCultivation = Objects.requireNonNull(refreshCultivation, "refreshCultivation");
        this.mainThread = Objects.requireNonNull(mainThread, "mainThread");
        this.playerLookup = Objects.requireNonNull(playerLookup, "playerLookup");
        this.inventoryFactory = Objects.requireNonNull(inventoryFactory, "inventoryFactory");
        this.itemFactory = Objects.requireNonNull(itemFactory, "itemFactory");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    @Override
    public void open(Player player, String interactionId, UUID npcId, String providerId) {
        Objects.requireNonNull(player, "player");
        PlayerLoginResult session = sessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("§c角色资料尚未加载，请稍后重试。");
            return;
        }
        if (!bindings.isCurrent(interactionId, npcId, providerId)) {
            player.sendMessage("§e该 NPC 的任务绑定已失效，请重新交互。");
            return;
        }

        UUID generation = UUID.randomUUID();
        UUID playerId = player.getUniqueId();
        QuestProviderInventoryHolder previous = openMenus.remove(playerId);
        if (previous != null
                && player.getOpenInventory().getTopInventory().getHolder() == previous) {
            player.closeInventory();
        }
        QuestProviderInventoryHolder holder = new QuestProviderInventoryHolder(
                generation,
                playerId,
                session.account().accountId(),
                session.currentLife().lifeId(),
                interactionId,
                npcId,
                providerId);
        Inventory inventory = inventoryFactory.create(
                holder, INVENTORY_SIZE, styled("任务委托", NamedTextColor.GOLD, true));
        holder.attach(inventory);
        generations.put(playerId, generation);
        openMenus.put(playerId, holder);
        renderLoading(holder);
        player.openInventory(inventory);
        refresh(player, holder);
    }

    @EventHandler
    public void onClick(InventoryClickEvent event) {
        Inventory top = event.getView().getTopInventory();
        if (!(top.getHolder() instanceof QuestProviderInventoryHolder holder)) {
            return;
        }
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)
                || !player.getUniqueId().equals(holder.playerId())
                || !validateCurrent(player, holder)) {
            return;
        }
        if (holder.busy()) {
            return;
        }
        int slot = event.getRawSlot();
        if (slot < 0 || slot >= INVENTORY_SIZE) {
            return;
        }
        if (slot < CONTENT_SIZE) {
            if (holder.view() == QuestProviderInventoryHolder.View.LIST && event.isLeftClick()) {
                holder.questIdAt(slot).ifPresent(questId -> {
                    holder.showDetail(questId);
                    render(holder);
                });
            }
            return;
        }
        if (slot == CLOSE_SLOT) {
            player.closeInventory();
        } else if (slot == REFRESH_SLOT) {
            refresh(player, holder);
        } else if (holder.view() == QuestProviderInventoryHolder.View.LIST) {
            handleListButton(holder, slot);
        } else if (slot == BACK_SLOT) {
            holder.showList();
            render(holder);
        } else if (slot == PRIMARY_SLOT) {
            mutate(player, holder);
        }
    }

    @EventHandler
    public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder()
                instanceof QuestProviderInventoryHolder) {
            event.setCancelled(true);
        }
    }

    @EventHandler
    public void onClose(InventoryCloseEvent event) {
        Inventory top = event.getView().getTopInventory();
        if (!(top.getHolder() instanceof QuestProviderInventoryHolder holder)) {
            return;
        }
        openMenus.remove(holder.playerId(), holder);
        generations.remove(holder.playerId(), holder.generation());
    }

    public void clearPlayer(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        generations.remove(playerId);
        QuestProviderInventoryHolder holder = openMenus.remove(playerId);
        Player player = playerLookup.apply(playerId);
        if (holder != null
                && player != null
                && player.getOpenInventory().getTopInventory().getHolder() == holder) {
            player.closeInventory();
        }
    }

    private void handleListButton(QuestProviderInventoryHolder holder, int slot) {
        if (slot == PREVIOUS_SLOT && holder.page() > 1) {
            holder.setPage(holder.page() - 1);
            render(holder);
        } else if (slot == NEXT_SLOT && holder.page() < holder.model().pageCount()) {
            holder.setPage(holder.page() + 1);
            render(holder);
        }
    }

    private void refresh(Player player, QuestProviderInventoryHolder holder) {
        if (!validateCurrent(player, holder) || !holder.beginOperation()) {
            return;
        }
        render(holder);
        quests.refresh(
                        holder.playerId(),
                        holder.accountId(),
                        holder.lifeId(),
                        holder.providerId())
                .whenComplete((state, error) -> dispatch(() -> finishRefresh(player, holder, state, error)));
    }

    private void finishRefresh(
            Player player,
            QuestProviderInventoryHolder holder,
            QuestInteractionState state,
            Throwable error) {
        holder.finishOperation();
        if (!isCurrent(holder) || !player.isOnline()) {
            return;
        }
        if (error != null) {
            player.sendMessage("§c读取任务失败，请稍后重试。");
            logFailure("quest_gui_refresh_failed", holder, error);
            render(holder);
            return;
        }
        try {
            QuestProviderMenuModel model = QuestProviderMenuModel.from(state, holder.providerId());
            if (holder.update(model)) {
                statePublisher.accept(holder.playerId(), state);
            }
        } catch (RuntimeException invalid) {
            player.sendMessage("§c任务数据无效，界面已关闭。");
            logFailure("quest_gui_projection_rejected", holder, invalid);
            player.closeInventory();
            return;
        }
        if (!validateCurrent(player, holder)) {
            return;
        }
        render(holder);
    }

    private void mutate(Player player, QuestProviderInventoryHolder holder) {
        String questId = holder.selectedQuestId().orElse(null);
        if (questId == null) {
            return;
        }
        QuestProviderMenuModel.QuestEntry quest = holder.model().findQuest(questId).orElse(null);
        if (quest == null || !holder.beginOperation()) {
            return;
        }
        QuestProviderMenuModel.PrimaryAction action = quest.primaryAction();
        UUID operationId = UUID.randomUUID();
        java.util.concurrent.CompletableFuture<QuestMutationResult> request;
        if (action == QuestProviderMenuModel.PrimaryAction.ACCEPT) {
            request = quests.accept(
                    holder.playerId(), holder.accountId(), holder.lifeId(),
                    quest.questId(), holder.providerId(), operationId);
        } else if (action == QuestProviderMenuModel.PrimaryAction.TURN_IN) {
            List<UUID> itemIds;
            try {
                itemIds = List.copyOf(inventoryItemIds.apply(player));
            } catch (RuntimeException invalidInventory) {
                holder.finishOperation();
                player.sendMessage("§c背包中的实体物品数据异常，任务未提交。");
                reconcileItems.accept(holder.playerId());
                render(holder);
                return;
            }
            request = quests.turnIn(
                    holder.playerId(), holder.accountId(), holder.lifeId(),
                    quest.questId(), holder.providerId(), operationId, itemIds);
        } else {
            holder.finishOperation();
            render(holder);
            return;
        }
        render(holder);
        request.whenComplete((result, error) -> dispatch(() -> finishMutation(
                player, holder, action, operationId, result, error)));
    }

    private void finishMutation(
            Player player,
            QuestProviderInventoryHolder holder,
            QuestProviderMenuModel.PrimaryAction action,
            UUID operationId,
            QuestMutationResult result,
            Throwable error) {
        holder.finishOperation();
        if (action == QuestProviderMenuModel.PrimaryAction.TURN_IN) {
            reconcileItems.accept(holder.playerId());
        }
        if (error != null || result == null || !operationId.equals(result.operationId())) {
            if (isCurrent(holder) && player.isOnline()) {
                player.sendMessage(mutationFailureMessage(action, error));
                render(holder);
                refresh(player, holder);
            }
            logFailure("quest_gui_mutation_failed", holder, error);
            return;
        }
        QuestInteractionState state = result.interactionState();
        if (!holder.accountId().equals(state.accountId()) || !holder.lifeId().equals(state.lifeId())) {
            logFailure("quest_gui_mutation_rejected", holder, new IllegalStateException("stale account or life"));
            return;
        }
        statePublisher.accept(holder.playerId(), state);
        if (action == QuestProviderMenuModel.PrimaryAction.TURN_IN) {
            refreshCultivation.accept(holder.playerId());
        }
        if (!isCurrent(holder) || !player.isOnline() || !validateCurrent(player, holder)) {
            return;
        }
        try {
            holder.update(QuestProviderMenuModel.from(state, holder.providerId()));
        } catch (RuntimeException invalid) {
            player.sendMessage("§c任务数据无效，界面已关闭。");
            logFailure("quest_gui_projection_rejected", holder, invalid);
            player.closeInventory();
            return;
        }
        player.sendMessage(action == QuestProviderMenuModel.PrimaryAction.ACCEPT
                ? "§a任务已接取。"
                : "§a任务已提交。"
        );
        render(holder);
    }

    private boolean validateCurrent(Player player, QuestProviderInventoryHolder holder) {
        if (!isCurrent(holder)
                || !sameSession(holder)
                || !bindings.isCurrent(holder.interactionId(), holder.npcId(), holder.providerId())) {
            if (player.isOnline()) {
                player.sendMessage("§e任务界面已失效，请重新右键 NPC。");
                player.closeInventory();
            }
            return false;
        }
        return true;
    }

    private boolean sameSession(QuestProviderInventoryHolder holder) {
        PlayerLoginResult current = sessions.findByMinecraftUuid(holder.playerId()).orElse(null);
        return current != null
                && current.account().accountId().equals(holder.accountId())
                && current.currentLife().lifeId().equals(holder.lifeId());
    }

    private boolean isCurrent(QuestProviderInventoryHolder holder) {
        return openMenus.get(holder.playerId()) == holder
                && holder.generation().equals(generations.get(holder.playerId()));
    }

    private void renderLoading(QuestProviderInventoryHolder holder) {
        fill(holder.getInventory());
        holder.getInventory().setItem(
                REFRESH_SLOT,
                itemFactory.create(new MenuItemSpec(
                        Material.CLOCK,
                        1,
                        styled("读取任务中...", NamedTextColor.YELLOW, false),
                        List.of())));
    }

    private void render(QuestProviderInventoryHolder holder) {
        if (!holder.loaded()) {
            renderLoading(holder);
            return;
        }
        fill(holder.getInventory());
        if (holder.view() == QuestProviderInventoryHolder.View.LIST) {
            renderList(holder);
        } else {
            renderDetail(holder);
        }
        holder.getInventory().setItem(
                REFRESH_SLOT,
                itemFactory.create(new MenuItemSpec(
                        holder.busy() ? Material.YELLOW_STAINED_GLASS_PANE : Material.CLOCK,
                        1,
                        styled(holder.busy() ? "同步中" : "刷新", NamedTextColor.YELLOW, false),
                        List.of())));
        holder.getInventory().setItem(
                CLOSE_SLOT,
                itemFactory.create(new MenuItemSpec(
                        Material.BARRIER,
                        1,
                        styled("关闭", NamedTextColor.RED, false),
                        List.of())));
    }

    private void renderList(QuestProviderInventoryHolder holder) {
        holder.clearQuestSlots();
        List<QuestProviderMenuModel.QuestEntry> quests = holder.model().page(holder.page());
        for (int slot = 0; slot < quests.size(); slot++) {
            QuestProviderMenuModel.QuestEntry quest = quests.get(slot);
            holder.getInventory().setItem(slot, itemFactory.create(listItem(quest)));
            if (quest.viewable()) {
                holder.bindQuestSlot(slot, quest.questId());
            }
        }
        if (holder.page() > 1) {
            holder.getInventory().setItem(PREVIOUS_SLOT, navigation(Material.ARROW, "上一页"));
        }
        if (holder.page() < holder.model().pageCount()) {
            holder.getInventory().setItem(NEXT_SLOT, navigation(Material.ARROW, "下一页"));
        }
    }

    private void renderDetail(QuestProviderInventoryHolder holder) {
        QuestProviderMenuModel.QuestEntry quest = holder.model()
                .findQuest(holder.selectedQuestId().orElseThrow())
                .orElseThrow();
        holder.getInventory().setItem(DETAIL_HEADER_SLOT, itemFactory.create(detailHeader(quest)));
        for (int slot = DETAIL_DIVIDER_START; slot <= DETAIL_DIVIDER_END; slot++) {
            holder.getInventory().setItem(slot, filler());
        }
        for (int index = 0; index < quest.objectives().size(); index++) {
            QuestObjectiveSnapshot objective = quest.objectives().get(index);
            holder.getInventory().setItem(
                    DETAIL_OBJECTIVE_START + index,
                    itemFactory.create(objectiveItem(objective)));
        }
        holder.getInventory().setItem(
                DETAIL_REWARD_SLOT,
                itemFactory.create(rewardItem(quest.rewardPreviews())));
        holder.getInventory().setItem(BACK_SLOT, navigation(Material.ARROW, "返回任务列表"));
        holder.getInventory().setItem(PRIMARY_SLOT, itemFactory.create(primaryItem(quest, holder.busy())));
    }

    private MenuItemSpec listItem(QuestProviderMenuModel.QuestEntry quest) {
        NamedTextColor color = stateColor(quest.state());
        Material material = quest.bookKind() == QuestProviderMenuModel.BookKind.BOOK
                ? Material.BOOK
                : Material.WRITTEN_BOOK;
        Component prompt = quest.viewable()
                ? styled("点击查看！", NamedTextColor.YELLOW, false)
                : styled("暂未解锁", NamedTextColor.RED, false);
        return new MenuItemSpec(material, 1, styled(quest.title(), color, isImportant(quest.state())), List.of(prompt));
    }

    private MenuItemSpec detailHeader(QuestProviderMenuModel.QuestEntry quest) {
        List<Component> lore = new ArrayList<>();
        if (!quest.description().isBlank()) {
            for (String line : quest.description().split("\\R", -1)) {
                lore.add(styled(line, NamedTextColor.GRAY, false));
            }
        }
        lore.add(styled("状态：" + stateText(quest.state()), stateColor(quest.state()), false));
        Material material = quest.bookKind() == QuestProviderMenuModel.BookKind.BOOK
                ? Material.BOOK
                : Material.WRITTEN_BOOK;
        return new MenuItemSpec(material, 1, styled(quest.title(), stateColor(quest.state()), true), lore);
    }

    private static MenuItemSpec objectiveItem(QuestObjectiveSnapshot objective) {
        Material material = switch (objective.objectiveType()) {
            case "item_delivery" -> Material.CHEST;
            case "mythicmob_kill_count" -> Material.IRON_SWORD;
            case "technique_layer_reached" -> Material.ENCHANTED_BOOK;
            case "realm_level_reached" -> Material.NETHER_STAR;
            case "current_life_spirit_root_present" -> Material.AMETHYST_SHARD;
            default -> Material.PAPER;
        };
        NamedTextColor color = objective.completed() ? NamedTextColor.GREEN : NamedTextColor.WHITE;
        return new MenuItemSpec(
                material,
                1,
                styled(objective.title(), color, objective.completed()),
                List.of(styled(QuestProviderMenuModel.progressText(objective), color, false)));
    }

    private static MenuItemSpec rewardItem(List<QuestRewardPreview> rewards) {
        List<Component> lore = rewards.isEmpty()
                ? List.of(styled("无", NamedTextColor.GRAY, false))
                : rewards.stream()
                        .map(reward -> styled(rewardText(reward), NamedTextColor.GREEN, false))
                        .toList();
        return new MenuItemSpec(
                Material.CHEST,
                1,
                styled("任务奖励", NamedTextColor.GOLD, true),
                lore);
    }

    private static MenuItemSpec primaryItem(QuestProviderMenuModel.QuestEntry quest, boolean busy) {
        if (busy) {
            return new MenuItemSpec(
                    Material.YELLOW_STAINED_GLASS_PANE,
                    1,
                    styled("处理中", NamedTextColor.YELLOW, false),
                    List.of());
        }
        return switch (quest.primaryAction()) {
            case ACCEPT -> action(Material.LIME_CONCRETE, "确认接取", NamedTextColor.GREEN);
            case TURN_IN -> action(Material.LIME_CONCRETE, "确认提交", NamedTextColor.GREEN);
            case DISABLED_ACTIVE -> action(Material.GRAY_DYE, "任务尚未完成", NamedTextColor.GRAY);
            case DISABLED_ACCEPT_ELSEWHERE -> action(
                    Material.GRAY_DYE, "请前往任务发布者接取", NamedTextColor.GRAY);
            case DISABLED_TURN_IN_ELSEWHERE -> action(
                    Material.GRAY_DYE, "请前往交付 NPC", NamedTextColor.GRAY);
            case DISABLED_LOCKED -> action(Material.RED_STAINED_GLASS_PANE, "暂未解锁", NamedTextColor.RED);
            case DISABLED_COMPLETED -> action(Material.GRAY_DYE, "任务已完成", NamedTextColor.GRAY);
        };
    }

    private ItemStack navigation(Material material, String text) {
        return itemFactory.create(action(material, text, NamedTextColor.YELLOW));
    }

    private static MenuItemSpec action(Material material, String text, NamedTextColor color) {
        return new MenuItemSpec(material, 1, styled(text, color, true), List.of());
    }

    private void fill(Inventory inventory) {
        inventory.clear();
        for (int slot = 0; slot < INVENTORY_SIZE; slot++) {
            inventory.setItem(slot, filler());
        }
    }

    private ItemStack filler() {
        return itemFactory.create(new MenuItemSpec(
                Material.GRAY_STAINED_GLASS_PANE,
                1,
                styled("", NamedTextColor.GRAY, false),
                List.of()));
    }

    private static ItemStack createItem(MenuItemSpec spec) {
        ItemStack item = new ItemStack(spec.material(), spec.amount());
        ItemMeta meta = item.getItemMeta();
        meta.displayName(spec.name());
        meta.lore(spec.lore());
        item.setItemMeta(meta);
        return item;
    }

    private static Component styled(String text, NamedTextColor color, boolean bold) {
        return Component.text(text)
                .color(color)
                .decoration(TextDecoration.BOLD, bold)
                .decoration(TextDecoration.ITALIC, TextDecoration.State.FALSE);
    }

    private static NamedTextColor stateColor(String state) {
        return switch (state) {
            case "ready_to_turn_in" -> NamedTextColor.GREEN;
            case "active" -> NamedTextColor.AQUA;
            case "available" -> NamedTextColor.YELLOW;
            case "unavailable" -> NamedTextColor.RED;
            case "completed" -> NamedTextColor.GRAY;
            default -> NamedTextColor.WHITE;
        };
    }

    private static boolean isImportant(String state) {
        return "ready_to_turn_in".equals(state) || "available".equals(state);
    }

    private static String stateText(String state) {
        return switch (state) {
            case "ready_to_turn_in" -> "可提交";
            case "active" -> "进行中";
            case "available" -> "可接取";
            case "unavailable" -> "暂未解锁";
            case "completed" -> "已完成";
            default -> state;
        };
    }

    private static String rewardText(QuestRewardPreview reward) {
        return switch (reward.kind()) {
            case "fixed_item" -> reward.itemCode() + " ×" + reward.quantity();
            case "unrefined_cultivation" -> "未炼化修为 ×" + reward.cultivationAmount();
            default -> reward.rewardId();
        };
    }

    private void dispatch(Runnable action) {
        try {
            mainThread.accept(action);
        } catch (RuntimeException error) {
            logger.warn("quest_gui_main_thread_dispatch_failed", error);
        }
    }

    private void logFailure(String event, QuestProviderInventoryHolder holder, Throwable error) {
        logger.warn(event
                + " minecraft_uuid=" + holder.playerId()
                + " provider_id=" + holder.providerId()
                + " reason=" + message(error));
    }

    private static String mutationFailureMessage(
            QuestProviderMenuModel.PrimaryAction action, Throwable error) {
        Throwable cause = unwrap(error);
        if (cause instanceof GameServiceException serviceError
                && "quest.not_ready".equals(serviceError.code())) {
            return "§e任务目标或背包材料已经变化，请重新确认。";
        }
        return action == QuestProviderMenuModel.PrimaryAction.ACCEPT
                ? "§c任务接取失败，请稍后重试。"
                : "§c任务提交失败，请稍后重试。";
    }

    private static String message(Throwable error) {
        if (error == null) {
            return "invalid_response";
        }
        Throwable cause = unwrap(error);
        return cause.getMessage() == null ? cause.getClass().getSimpleName() : cause.getMessage();
    }

    private static Throwable unwrap(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }

    @Override
    public void close() {
        List<QuestProviderInventoryHolder> holders = List.copyOf(openMenus.values());
        openMenus.clear();
        generations.clear();
        holders.forEach(holder -> {
            Player player = playerLookup.apply(holder.playerId());
            if (player != null
                    && player.getOpenInventory().getTopInventory().getHolder() == holder) {
                player.closeInventory();
            }
        });
        HandlerList.unregisterAll(this);
    }

    @FunctionalInterface
    public interface ProviderBindingValidator {
        boolean isCurrent(String interactionId, UUID npcId, String providerId);
    }

    @FunctionalInterface
    interface InventoryFactory {
        Inventory create(InventoryHolder holder, int size, Component title);
    }

    @FunctionalInterface
    interface MenuItemFactory {
        ItemStack create(MenuItemSpec spec);
    }

    record MenuItemSpec(Material material, int amount, Component name, List<Component> lore) {
        MenuItemSpec {
            Objects.requireNonNull(material, "material");
            if (amount <= 0) {
                throw new IllegalArgumentException("Menu item amount must be positive");
            }
            Objects.requireNonNull(name, "name");
            lore = List.copyOf(lore);
        }
    }
}
