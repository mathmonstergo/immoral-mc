package com.immortalmc.adapter.storage;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.StorageSnapshot;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.List;
import java.util.UUID;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

class RegionalStorageAccessPolicyTest {
    private static final UUID PLAYER_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID ACCOUNT_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");

    @Test
    void requiresSameCurrentLifeAreaAndPermission() {
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(login(LIFE_ID));
        Player player = mock(Player.class);
        when(player.getUniqueId()).thenReturn(PLAYER_ID);
        when(player.hasPermission("immortalmc.storage")).thenReturn(true);
        RegionalStorageInventoryHolder holder = holder();
        RegionalStorageAccessPolicy policy = new RegionalStorageAccessPolicy(sessions);

        assertTrue(policy.allows(player, holder, "qi-field"));
        assertFalse(policy.allows(player, holder, "foundation-field"));

        when(player.hasPermission("immortalmc.storage")).thenReturn(false);
        assertFalse(policy.allows(player, holder, "qi-field"));

        sessions.store(login(UUID.fromString("30000000-0000-0000-0000-000000000002")));
        when(player.hasPermission("immortalmc.storage")).thenReturn(true);
        assertFalse(policy.allows(player, holder, "qi-field"));
    }

    private static PlayerLoginResult login(UUID lifeId) {
        return new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Tester"),
                new LifeSnapshot(lifeId, ACCOUNT_ID, 1, "alive", null));
    }

    private static RegionalStorageInventoryHolder holder() {
        return new RegionalStorageInventoryHolder(
                PLAYER_ID,
                ACCOUNT_ID,
                LIFE_ID,
                "qi-field",
                new StorageSnapshot(
                        1,
                        LIFE_ID,
                        "qi-field",
                        "sha256:storage",
                        "immortalmc.storage",
                        1,
                        9,
                        45,
                        0,
                        List.of()));
    }
}
