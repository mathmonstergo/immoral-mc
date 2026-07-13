package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public record CitizensNpcSelection(
        int numericId,
        String name,
        UUID persistentUuid,
        Optional<EntityInteractionEntity> spawnedEntity) {
    public CitizensNpcSelection {
        Objects.requireNonNull(name, "name");
        Objects.requireNonNull(persistentUuid, "persistentUuid");
        Objects.requireNonNull(spawnedEntity, "spawnedEntity");
        if (numericId < 0) {
            throw new IllegalArgumentException("numericId must not be negative");
        }
        if (name.isBlank()) {
            throw new IllegalArgumentException("name must not be blank");
        }
    }
}
