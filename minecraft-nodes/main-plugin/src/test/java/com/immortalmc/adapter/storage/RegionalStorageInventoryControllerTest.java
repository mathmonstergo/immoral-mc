package com.immortalmc.adapter.storage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.StorageMoveRequest;
import com.immortalmc.adapter.client.StorageMoveSnapshot;
import com.immortalmc.adapter.client.StorageSlotSnapshot;
import com.immortalmc.adapter.client.StorageSnapshot;
import com.immortalmc.adapter.cultivation.CultivationAreaResolver;
import com.immortalmc.adapter.item.PhysicalInventoryAccess;
import com.immortalmc.adapter.item.PhysicalItemIdentity;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicReference;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.junit.jupiter.api.Test;

class RegionalStorageInventoryControllerTest {
    private static final UUID PLAYER_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ACCOUNT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void confirmedDepositReconcilesInventoryAndRefreshesTrackedQuest() {
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Tester"),
                new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
        RecordingGateway gateway = new RecordingGateway();
        PhysicalInventoryAccess physicalInventory = mock(PhysicalInventoryAccess.class);
        ItemStack clicked = mock(ItemStack.class);
        when(physicalInventory.identity(clicked))
                .thenReturn(Optional.of(PhysicalItemIdentity.item(ITEM_ID, "foundation_pill")));
        when(physicalInventory.create(any(ItemInstanceSnapshot.class))).thenReturn(mock(ItemStack.class));

        Player player = mock(Player.class);
        World world = mock(World.class);
        when(world.getName()).thenReturn("world");
        when(player.getUniqueId()).thenReturn(PLAYER_ID);
        when(player.isOnline()).thenReturn(true);
        when(player.getWorld()).thenReturn(world);
        when(player.getLocation()).thenReturn(new Location(world, 0, 64, 0));
        when(player.hasPermission("immortalmc.storage")).thenReturn(true);

        Inventory inventory = mock(Inventory.class);
        InventoryView view = mock(InventoryView.class);
        when(player.openInventory(inventory)).thenReturn(view);
        when(view.getTopInventory()).thenReturn(inventory);
        AtomicReference<RegionalStorageInventoryHolder> holder = new AtomicReference<>();
        when(inventory.getHolder()).thenAnswer(ignored -> holder.get());
        List<UUID> reconciles = new ArrayList<>();
        List<UUID> questRefreshes = new ArrayList<>();
        RegionalStorageInventoryController controller = new RegionalStorageInventoryController(
                gateway,
                sessions,
                areaResolver(),
                physicalInventory,
                reconciles::add,
                questRefreshes::add,
                Runnable::run,
                ignored -> player,
                (createdHolder, size, title) -> {
                    assertEquals(54, size);
                    holder.set((RegionalStorageInventoryHolder) createdHolder);
                    return inventory;
                },
                (material, name, lore) -> mock(ItemStack.class),
                new RecordingAdapterLogger());

        controller.open(player);
        InventoryClickEvent deposit = mock(InventoryClickEvent.class);
        when(deposit.getView()).thenReturn(view);
        when(deposit.getWhoClicked()).thenReturn(player);
        when(deposit.getRawSlot()).thenReturn(60);
        when(deposit.getCurrentItem()).thenReturn(clicked);

        controller.onClick(deposit);

        verify(deposit).setCancelled(true);
        assertEquals(1, gateway.moves.size());
        assertEquals("deposit", gateway.moves.getFirst().moveKind());
        assertEquals(List.of(PLAYER_ID, PLAYER_ID), reconciles);
        assertEquals(List.of(PLAYER_ID), questRefreshes);
        assertEquals(1, holder.get().snapshot().revision());
    }

    private static CultivationAreaResolver areaResolver() {
        ConfigurationSection config = mock(ConfigurationSection.class);
        when(config.getMapList("cultivation.areas")).thenReturn(List.of(Map.of(
                "area-id", "village",
                "world", "world",
                "min", Map.of("x", -10, "y", 0, "z", -10),
                "max", Map.of("x", 10, "y", 100, "z", 10))));
        return CultivationAreaResolver.from(config);
    }

    private static StorageSnapshot snapshot(long revision, List<StorageSlotSnapshot> slots) {
        return new StorageSnapshot(
                1,
                LIFE_ID,
                "village",
                "sha256:catalog",
                "immortalmc.storage",
                1,
                1,
                45,
                revision,
                slots);
    }

    private static ItemInstanceSnapshot storedItem() {
        return new ItemInstanceSnapshot(
                1,
                ITEM_ID,
                "foundation_pill",
                1,
                null,
                "owned",
                "storage");
    }

    private static final class RecordingGateway implements RegionalStorageGateway {
        private final List<StorageMoveRequest> moves = new ArrayList<>();

        @Override
        public CompletableFuture<StorageSnapshot> fetchStorage(UUID accountId, String areaId, int page) {
            return CompletableFuture.completedFuture(snapshot(0, List.of()));
        }

        @Override
        public CompletableFuture<StorageMoveSnapshot> moveStorage(
                UUID accountId,
                String areaId,
                StorageMoveRequest request,
                UUID operationId) {
            moves.add(request);
            StorageSnapshot result = snapshot(1, List.of(new StorageSlotSnapshot(0, storedItem())));
            return CompletableFuture.completedFuture(new StorageMoveSnapshot(
                    1,
                    operationId,
                    request.moveKind(),
                    request.itemInstanceId(),
                    result));
        }
    }
}
