package com.immortalmc.adapter.citizens;

import java.util.Optional;
import java.util.UUID;
import org.bukkit.entity.Entity;

@FunctionalInterface
public interface CitizensNpcResolver {
    Optional<UUID> persistentNpcUuid(Entity entity);

    default boolean isCitizensNpc(Entity entity) {
        return persistentNpcUuid(entity).isPresent();
    }

    static CitizensNpcResolver unavailable() {
        return entity -> Optional.empty();
    }
}
