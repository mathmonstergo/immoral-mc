package com.immortalmc.adapter.session;

import static org.junit.jupiter.api.Assertions.assertEquals;
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
}
