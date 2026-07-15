package com.immortalmc.adapter.mythicmobs;

import java.util.Objects;
import java.util.Optional;
import org.bukkit.event.HandlerList;
import org.bukkit.event.Listener;

public final class MythicMobsIntegrationHandle implements AutoCloseable {
    private final Listener listener;

    private MythicMobsIntegrationHandle(Listener listener) {
        this.listener = listener;
    }

    public static MythicMobsIntegrationHandle unavailable() {
        return new MythicMobsIntegrationHandle(null);
    }

    public static MythicMobsIntegrationHandle available(Listener listener) {
        return new MythicMobsIntegrationHandle(Objects.requireNonNull(listener, "listener"));
    }

    public boolean available() {
        return listener != null;
    }

    public Optional<Listener> listener() {
        return Optional.ofNullable(listener);
    }

    @Override
    public void close() {
        if (listener != null) {
            HandlerList.unregisterAll(listener);
        }
    }
}
