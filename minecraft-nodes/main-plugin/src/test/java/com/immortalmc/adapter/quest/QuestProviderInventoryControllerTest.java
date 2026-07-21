package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicReference;
import net.kyori.adventure.text.TextComponent;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.junit.jupiter.api.Test;

class QuestProviderInventoryControllerTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void rendersReadOnlyListAndDetailThenTurnsInExactCurrentInventory() {
        Harness harness = new Harness("ready_to_turn_in", "turn_in");

        harness.controller.open(harness.player, "interaction", NPC_ID, "old-man");

        assertEquals(54, harness.slots.size());
        QuestProviderInventoryController.MenuItemSpec list = harness.specAt(0);
        assertEquals(Material.WRITTEN_BOOK, list.material());
        assertEquals(1, list.lore().size());
        assertEquals("点击查看！", ((TextComponent) list.lore().getFirst()).content());

        InventoryClickEvent openDetail = harness.click(0, true);
        harness.controller.onClick(openDetail);
        verify(openDetail).setCancelled(true);
        for (int slot = 9; slot <= 17; slot++) {
            assertEquals(Material.GRAY_STAINED_GLASS_PANE, harness.specAt(slot).material());
        }
        assertEquals(Material.LIME_CONCRETE, harness.specAt(53).material());

        InventoryClickEvent submit = harness.click(53, true);
        harness.controller.onClick(submit);

        assertEquals(1, harness.service.turnInCalls);
        assertEquals(List.of(ITEM_ID), harness.service.presentedItemIds);
        assertEquals(Material.GRAY_DYE, harness.specAt(53).material());
        assertEquals(1, harness.reconciles);
        assertEquals(1, harness.cultivationRefreshes);

        InventoryClickEvent bottomShiftOrHotbar = harness.click(60, true);
        harness.controller.onClick(bottomShiftOrHotbar);
        verify(bottomShiftOrHotbar).setCancelled(true);
        assertEquals(1, harness.service.turnInCalls);

        InventoryDragEvent drag = mock(InventoryDragEvent.class);
        when(drag.getView()).thenReturn(harness.view);
        harness.controller.onDrag(drag);
        verify(drag).setCancelled(true);
    }

    @Test
    void acceptsAvailableQuestAndClearPlayerClosesOnlyCurrentMenu() {
        Harness harness = new Harness("available", "offer");
        harness.controller.open(harness.player, "interaction", NPC_ID, "old-man");
        harness.controller.onClick(harness.click(0, true));
        harness.controller.onClick(harness.click(53, true));

        assertEquals(1, harness.service.acceptCalls);
        assertEquals(Material.GRAY_DYE, harness.specAt(53).material());

        harness.controller.clearPlayer(PLAYER_ID);
        verify(harness.player).closeInventory();
        assertTrue(harness.holder.get().busy() == false);
    }

    @Test
    void lockedQuestIsVisibleRedAndCannotOpen() {
        Harness harness = new Harness("unavailable", "none");
        harness.controller.open(harness.player, "interaction", NPC_ID, "old-man");

        QuestProviderInventoryController.MenuItemSpec locked = harness.specAt(0);
        assertEquals(Material.BOOK, locked.material());
        assertEquals("暂未解锁", ((TextComponent) locked.lore().getFirst()).content());
        harness.controller.onClick(harness.click(0, true));

        assertEquals(QuestProviderInventoryHolder.View.LIST, harness.holder.get().view());
        verify(harness.player, never()).sendMessage("§a任务已接取。");
    }

    @Test
    void invalidMutationProjectionIsReportedAndClosesTheMenu() {
        Harness harness = new Harness("ready_to_turn_in", "turn_in");
        harness.service.mutationProviderId = "other-provider";
        harness.controller.open(harness.player, "interaction", NPC_ID, "old-man");
        harness.controller.onClick(harness.click(0, true));

        harness.controller.onClick(harness.click(53, true));

        verify(harness.player).sendMessage("§c任务数据无效，界面已关闭。");
        verify(harness.player).closeInventory();
        assertTrue(harness.logger.messagesAt("warn").stream()
                .anyMatch(message -> message.startsWith("quest_gui_projection_rejected")));
    }

    private static final class Harness {
        private final PlayerSessionCache sessions = new PlayerSessionCache();
        private final FakeQuestService service;
        private final Player player = mock(Player.class);
        private final Inventory inventory = mock(Inventory.class);
        private final InventoryView view = mock(InventoryView.class);
        private final AtomicReference<QuestProviderInventoryHolder> holder = new AtomicReference<>();
        private final Map<Integer, ItemStack> slots = new HashMap<>();
        private final Map<ItemStack, QuestProviderInventoryController.MenuItemSpec> specs =
                new IdentityHashMap<>();
        private final RecordingAdapterLogger logger = new RecordingAdapterLogger();
        private int reconciles;
        private int cultivationRefreshes;
        private final QuestProviderInventoryController controller;

        private Harness(String state, String action) {
            sessions.store(new PlayerLoginResult(
                    new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Sensen"),
                    new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
            service = new FakeQuestService(state, action);
            when(player.getUniqueId()).thenReturn(PLAYER_ID);
            when(player.isOnline()).thenReturn(true);
            when(player.getOpenInventory()).thenReturn(view);
            when(view.getTopInventory()).thenReturn(inventory);
            when(inventory.getHolder()).thenAnswer(ignored -> holder.get());
            doAnswer(invocation -> {
                slots.clear();
                return null;
            }).when(inventory).clear();
            doAnswer(invocation -> {
                slots.put(invocation.getArgument(0), invocation.getArgument(1));
                return null;
            }).when(inventory).setItem(anyInt(), any(ItemStack.class));
            when(player.openInventory(inventory)).thenReturn(view);

            controller = new QuestProviderInventoryController(
                    sessions,
                    service,
                    (interactionId, npcId, providerId) -> true,
                    ignored -> List.of(ITEM_ID),
                    (playerId, projection) -> {},
                    ignored -> reconciles++,
                    ignored -> cultivationRefreshes++,
                    Runnable::run,
                    ignored -> player,
                    (createdHolder, size, title) -> {
                        assertEquals(54, size);
                        holder.set((QuestProviderInventoryHolder) createdHolder);
                        return inventory;
                    },
                    spec -> {
                        ItemStack item = mock(ItemStack.class);
                        specs.put(item, spec);
                        return item;
                    },
                    logger);
        }

        private QuestProviderInventoryController.MenuItemSpec specAt(int slot) {
            return specs.get(slots.get(slot));
        }

        private InventoryClickEvent click(int rawSlot, boolean left) {
            InventoryClickEvent event = mock(InventoryClickEvent.class);
            when(event.getView()).thenReturn(view);
            when(event.getWhoClicked()).thenReturn(player);
            when(event.getRawSlot()).thenReturn(rawSlot);
            when(event.isLeftClick()).thenReturn(left);
            return event;
        }
    }

    private static final class FakeQuestService implements QuestInteractionService {
        private QuestInteractionState current;
        private int acceptCalls;
        private int turnInCalls;
        private List<UUID> presentedItemIds = List.of();
        private String mutationProviderId = "old-man";

        private FakeQuestService(String state, String action) {
            current = state(state, action, 1);
        }

        @Override
        public CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId) {
            return CompletableFuture.completedFuture(current);
        }

        @Override
        public CompletableFuture<QuestMutationResult> accept(
                UUID playerId,
                UUID accountId,
                UUID lifeId,
                String questId,
                String providerId,
                UUID operationId) {
            acceptCalls++;
            current = state("active", "remind", 2);
            return CompletableFuture.completedFuture(result(operationId, current, List.of()));
        }

        @Override
        public CompletableFuture<QuestMutationResult> turnIn(
                UUID playerId,
                UUID accountId,
                UUID lifeId,
                String questId,
                String providerId,
                UUID operationId,
                List<UUID> inventoryItemInstanceIds) {
            turnInCalls++;
            presentedItemIds = List.copyOf(inventoryItemInstanceIds);
            current = state("completed", "talk", 2, mutationProviderId);
            return CompletableFuture.completedFuture(result(operationId, current, presentedItemIds));
        }

        private static QuestMutationResult result(
                UUID operationId, QuestInteractionState state, List<UUID> consumed) {
            return new QuestMutationResult(
                    operationId,
                    true,
                    state.providers().getFirst().quests().getFirst(),
                    state,
                    List.of(),
                    consumed);
        }

        private static QuestInteractionState state(String state, String action, long revision) {
            return state(state, action, revision, "old-man");
        }

        private static QuestInteractionState state(
                String state,
                String action,
                long revision,
                String providerId) {
            ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                    "quest",
                    "矿洞补给",
                    "收集矿洞里的玄铁。",
                    "side",
                    state,
                    action,
                    null,
                    List.of(new QuestObjectiveSnapshot(
                            "iron", "item_delivery", "玄铁", "mystic_iron", 20, 15,
                            "ready_to_turn_in".equals(state) || "completed".equals(state))),
                    List.of());
            return new QuestInteractionState(
                    2,
                    ACCOUNT_ID,
                    LIFE_ID,
                    new QuestRevisionVector(1, revision, revision, "sha256:definitions"),
                    List.of(new QuestProviderSnapshot(
                            providerId, "quest:" + state, List.of(quest), List.of("quest"), "quest", null)),
                    null,
                    2000);
        }
    }
}
