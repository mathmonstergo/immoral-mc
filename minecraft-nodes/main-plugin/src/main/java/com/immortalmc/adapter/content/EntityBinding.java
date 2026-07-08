package com.immortalmc.adapter.content;

import java.util.Objects;
import java.util.UUID;

public record EntityBinding(String worldName, UUID entityUuid) {
    public EntityBinding {
        Objects.requireNonNull(worldName, "worldName");
        Objects.requireNonNull(entityUuid, "entityUuid");
        if (worldName.isBlank()) {
            throw new IllegalArgumentException("worldName must not be blank");
        }
    }
}
