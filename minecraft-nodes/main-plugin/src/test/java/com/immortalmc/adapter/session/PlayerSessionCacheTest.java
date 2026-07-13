package com.immortalmc.adapter.session;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PlayerSessionCacheTest {
    @Test
    void storesSuccessfulLoginSnapshotByMinecraftUuid() {
        PlayerSessionCache cache = new PlayerSessionCache();
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        PlayerLoginResult result = new PlayerLoginResult(
                new AccountSnapshot(
                        UUID.fromString("10000000-0000-0000-0000-000000000001"), minecraftUuid, "Sensen"),
                new LifeSnapshot(
                        UUID.fromString("20000000-0000-0000-0000-000000000001"),
                        UUID.fromString("10000000-0000-0000-0000-000000000001"),
                        1,
                        "alive",
                        null));

        cache.store(result);

        assertTrue(cache.findByMinecraftUuid(minecraftUuid).isPresent());
        assertEquals(result, cache.findByMinecraftUuid(minecraftUuid).orElseThrow());
    }

    @Test
    void replacesCurrentLifeSnapshotForTheSamePlayer() {
        PlayerSessionCache cache = new PlayerSessionCache();
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        PlayerLoginResult first = result(minecraftUuid, UUID.fromString("20000000-0000-0000-0000-000000000001"));
        PlayerLoginResult replacement =
                result(minecraftUuid, UUID.fromString("20000000-0000-0000-0000-000000000002"));

        cache.store(first);
        cache.store(replacement);

        assertSame(replacement, cache.findByMinecraftUuid(minecraftUuid).orElseThrow());
    }

    @Test
    void removesPlayerSessionOnQuit() {
        PlayerSessionCache cache = new PlayerSessionCache();
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        cache.store(result(minecraftUuid, UUID.fromString("20000000-0000-0000-0000-000000000001")));

        cache.remove(minecraftUuid);

        assertTrue(cache.findByMinecraftUuid(minecraftUuid).isEmpty());
    }

    private static PlayerLoginResult result(UUID minecraftUuid, UUID lifeId) {
        UUID accountId = UUID.fromString("10000000-0000-0000-0000-000000000001");
        return new PlayerLoginResult(
                new AccountSnapshot(accountId, minecraftUuid, "Sensen"),
                new LifeSnapshot(lifeId, accountId, 1, "alive", null));
    }
}
