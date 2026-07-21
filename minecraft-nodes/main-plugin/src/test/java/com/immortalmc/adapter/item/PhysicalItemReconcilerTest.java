package com.immortalmc.adapter.item;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.ItemDeliveryConfirmationSnapshot;
import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import com.immortalmc.adapter.client.ItemInstancesSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.junit.jupiter.api.Test;

class PhysicalItemReconcilerTest {
    private static final UUID PLAYER_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ACCOUNT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID OWNED_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID PENDING_ID = UUID.fromString("50000000-0000-0000-0000-000000000001");

    @Test
    void appliesAuthoritativeInventoryAndConfirmsPendingDelivery() {
        PlayerSessionCache sessions = sessions();
        Player player = player();
        RecordingInventory inventory = new RecordingInventory();
        RecordingGateway gateway = new RecordingGateway(
                CompletableFuture.completedFuture(list(pending(PENDING_ID))),
                CompletableFuture.completedFuture(list(ownedInventory(OWNED_ID))));
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<UUID> questRefreshes = new ArrayList<>();
        PhysicalItemReconciler reconciler = new PhysicalItemReconciler(
                gateway,
                sessions,
                inventory,
                ignored -> player,
                questRefreshes::add,
                Runnable::run,
                logger);

        reconciler.reconcile(PLAYER_ID);

        assertEquals(Set.of(OWNED_ID, PENDING_ID), inventory.authoritativeIds);
        assertEquals(List.of(OWNED_ID, PENDING_ID), inventory.addedIds);
        assertEquals(List.of(PENDING_ID), gateway.confirmedIds);
        assertEquals(List.of(PLAYER_ID), questRefreshes);
        assertTrue(logger.messagesAt("info").getFirst().contains("removed=1 restored=1 confirmations=1"));
    }

    @Test
    void clearInvalidatesAnOutstandingReconciliationCompletion() {
        PlayerSessionCache sessions = sessions();
        Player player = player();
        RecordingInventory inventory = new RecordingInventory();
        CompletableFuture<ItemInstancesSnapshot> pending = new CompletableFuture<>();
        CompletableFuture<ItemInstancesSnapshot> owned = new CompletableFuture<>();
        RecordingGateway gateway = new RecordingGateway(pending, owned);
        PhysicalItemReconciler reconciler = new PhysicalItemReconciler(
                gateway,
                sessions,
                inventory,
                ignored -> player,
                ignored -> {},
                Runnable::run,
                new RecordingAdapterLogger());

        reconciler.reconcile(PLAYER_ID);
        reconciler.clearPlayer(PLAYER_ID);
        pending.complete(list(pending(PENDING_ID)));
        owned.complete(list(ownedInventory(OWNED_ID)));

        assertTrue(inventory.addedIds.isEmpty());
        assertTrue(gateway.confirmedIds.isEmpty());
    }

    @Test
    void failedDeliveryConfirmationDoesNotRefreshTrackedQuest() {
        PlayerSessionCache sessions = sessions();
        Player player = player();
        RecordingGateway gateway = new RecordingGateway(
                CompletableFuture.completedFuture(list(pending(PENDING_ID))),
                CompletableFuture.completedFuture(list(ownedInventory(OWNED_ID))),
                new IllegalStateException("confirmation failed"));
        List<UUID> questRefreshes = new ArrayList<>();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        PhysicalItemReconciler reconciler = new PhysicalItemReconciler(
                gateway,
                sessions,
                new RecordingInventory(),
                ignored -> player,
                questRefreshes::add,
                Runnable::run,
                logger);

        reconciler.reconcile(PLAYER_ID);

        assertTrue(questRefreshes.isEmpty());
        assertTrue(logger.messagesAt("warn").stream()
                .anyMatch(message -> message.startsWith("physical_item_delivery_confirmation_failed")));
    }

    private static PlayerSessionCache sessions() {
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Tester"),
                new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
        return sessions;
    }

    private static Player player() {
        Player player = mock(Player.class);
        when(player.getUniqueId()).thenReturn(PLAYER_ID);
        when(player.isOnline()).thenReturn(true);
        when(player.getInventory()).thenReturn(mock(PlayerInventory.class));
        return player;
    }

    private static ItemInstancesSnapshot list(ItemInstanceSnapshot item) {
        return new ItemInstancesSnapshot(1, LIFE_ID, List.of(item));
    }

    private static ItemInstanceSnapshot pending(UUID itemId) {
        return new ItemInstanceSnapshot(
                1, itemId, "technique_manual_yinqi", 1, "GF_YinqiShu_01", "pending_delivery", null);
    }

    private static ItemInstanceSnapshot ownedInventory(UUID itemId) {
        return new ItemInstanceSnapshot(
                1, itemId, "technique_manual_yinqi", 1, "GF_YinqiShu_01", "owned", "inventory");
    }

    private static final class RecordingGateway implements PhysicalItemGateway {
        private final CompletableFuture<ItemInstancesSnapshot> pending;
        private final CompletableFuture<ItemInstancesSnapshot> owned;
        private final RuntimeException confirmationError;
        private final List<UUID> confirmedIds = new ArrayList<>();

        private RecordingGateway(
                CompletableFuture<ItemInstancesSnapshot> pending,
                CompletableFuture<ItemInstancesSnapshot> owned) {
            this(pending, owned, null);
        }

        private RecordingGateway(
                CompletableFuture<ItemInstancesSnapshot> pending,
                CompletableFuture<ItemInstancesSnapshot> owned,
                RuntimeException confirmationError) {
            this.pending = pending;
            this.owned = owned;
            this.confirmationError = confirmationError;
        }

        @Override
        public CompletableFuture<ItemInstancesSnapshot> fetchPendingItemDeliveries(UUID accountId) {
            return pending;
        }

        @Override
        public CompletableFuture<ItemInstancesSnapshot> fetchInventoryItems(UUID accountId) {
            return owned;
        }

        @Override
        public CompletableFuture<ItemDeliveryConfirmationSnapshot> confirmItemDelivery(
                UUID accountId,
                UUID itemInstanceId) {
            confirmedIds.add(itemInstanceId);
            if (confirmationError != null) {
                return CompletableFuture.failedFuture(confirmationError);
            }
            return CompletableFuture.completedFuture(
                    new ItemDeliveryConfirmationSnapshot(1, ownedInventory(itemInstanceId)));
        }
    }

    private static final class RecordingInventory implements PhysicalInventoryAccess {
        private final List<UUID> addedIds = new ArrayList<>();
        private Set<UUID> authoritativeIds = Set.of();

        @Override
        public Optional<PhysicalItemIdentity> identity(ItemStack item) {
            return Optional.empty();
        }

        @Override
        public ItemStack create(ItemInstanceSnapshot snapshot) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<UUID> instanceIds(PlayerInventory inventory) {
            return List.of();
        }

        @Override
        public boolean contains(PlayerInventory inventory, UUID itemInstanceId) {
            return false;
        }

        @Override
        public boolean add(PlayerInventory inventory, ItemInstanceSnapshot snapshot) {
            addedIds.add(snapshot.itemInstanceId());
            return true;
        }

        @Override
        public boolean remove(PlayerInventory inventory, UUID itemInstanceId) {
            return false;
        }

        @Override
        public int removeUnexpected(PlayerInventory inventory, Set<UUID> authoritativeIds) {
            this.authoritativeIds = Set.copyOf(authoritativeIds);
            return 1;
        }
    }
}
