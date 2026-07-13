package com.immortalmc.adapter.session;

import com.immortalmc.adapter.client.PlayerLoginResult;
import java.util.Optional;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

public final class PlayerSessionCache {
    private final ConcurrentMap<UUID, PlayerLoginResult> sessionsByMinecraftUuid = new ConcurrentHashMap<>();

    public void store(PlayerLoginResult result) {
        Objects.requireNonNull(result, "result");
        sessionsByMinecraftUuid.put(result.account().minecraftUuid(), result);
    }

    public Optional<PlayerLoginResult> findByMinecraftUuid(UUID minecraftUuid) {
        return Optional.ofNullable(sessionsByMinecraftUuid.get(minecraftUuid));
    }

    public void remove(UUID minecraftUuid) {
        sessionsByMinecraftUuid.remove(Objects.requireNonNull(minecraftUuid, "minecraftUuid"));
    }

    public void clear() {
        sessionsByMinecraftUuid.clear();
    }
}
