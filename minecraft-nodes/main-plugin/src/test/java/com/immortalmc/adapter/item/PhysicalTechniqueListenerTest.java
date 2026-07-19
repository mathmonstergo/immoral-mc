package com.immortalmc.adapter.item;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.ItemInstanceSnapshot;
import com.immortalmc.adapter.client.LearnTechniqueSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.nio.charset.StandardCharsets;
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

class PhysicalTechniqueListenerTest {
    private static final UUID PLAYER_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ACCOUNT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID ITEM_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_TECHNIQUE_ID =
            UUID.fromString("50000000-0000-0000-0000-000000000001");

    @Test
    void coalescesConcurrentUseAndDerivesStableOperationIdFromItemIdentity() {
        PlayerSessionCache sessions = sessions();
        ItemStack item = mock(ItemStack.class);
        Player player = player();
        RecordingLearningGateway gateway = new RecordingLearningGateway();
        List<UUID> reconciled = new ArrayList<>();
        List<UUID> refreshed = new ArrayList<>();
        PhysicalTechniqueListener listener = new PhysicalTechniqueListener(
                gateway,
                sessions,
                new FixedInventory(item),
                reconciled::add,
                refreshed::add,
                Runnable::run,
                new RecordingAdapterLogger());

        assertTrue(listener.useManual(player, item));
        assertTrue(listener.useManual(player, item));

        UUID expectedOperationId = UUID.nameUUIDFromBytes(
                ("immortalmc:technique-learn:" + ITEM_ID).getBytes(StandardCharsets.UTF_8));
        assertEquals(List.of(expectedOperationId), gateway.operationIds);
        verify(player).sendMessage("§e正在研读秘籍，请稍候。");

        gateway.result.complete(new LearnTechniqueSnapshot(
                1,
                expectedOperationId,
                ITEM_ID,
                LIFE_TECHNIQUE_ID,
                "GF_YinqiShu_01",
                "引气术",
                0,
                "active"));

        assertEquals(List.of(PLAYER_ID), reconciled);
        assertEquals(List.of(PLAYER_ID), refreshed);
        verify(player).sendMessage("§a已学会功法：§f引气术 §7（第 0 层）");
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
        return player;
    }

    private static final class RecordingLearningGateway implements TechniqueLearningGateway {
        private final List<UUID> operationIds = new ArrayList<>();
        private final CompletableFuture<LearnTechniqueSnapshot> result = new CompletableFuture<>();

        @Override
        public CompletableFuture<LearnTechniqueSnapshot> learnTechnique(
                UUID accountId,
                UUID itemInstanceId,
                UUID operationId) {
            assertEquals(ACCOUNT_ID, accountId);
            assertEquals(ITEM_ID, itemInstanceId);
            operationIds.add(operationId);
            return result;
        }
    }

    private static final class FixedInventory implements PhysicalInventoryAccess {
        private final ItemStack manual;

        private FixedInventory(ItemStack manual) {
            this.manual = manual;
        }

        @Override
        public Optional<PhysicalItemIdentity> identity(ItemStack item) {
            return item == manual
                    ? Optional.of(PhysicalItemIdentity.techniqueManual(
                            ITEM_ID,
                            "technique_manual_yinqi",
                            "GF_YinqiShu_01",
                            1))
                    : Optional.empty();
        }

        @Override
        public ItemStack create(ItemInstanceSnapshot snapshot) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<UUID> instanceIds(PlayerInventory inventory) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean contains(PlayerInventory inventory, UUID itemInstanceId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean add(PlayerInventory inventory, ItemInstanceSnapshot snapshot) {
            throw new UnsupportedOperationException();
        }

        @Override
        public boolean remove(PlayerInventory inventory, UUID itemInstanceId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public int removeUnexpected(PlayerInventory inventory, Set<UUID> authoritativeIds) {
            throw new UnsupportedOperationException();
        }
    }
}
