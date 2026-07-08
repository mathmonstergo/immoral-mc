package com.immortalmc.adapter.content;

import java.util.Objects;

public record EntityInteractionEntity(EntityBinding binding, String entityType) {
    public EntityInteractionEntity {
        Objects.requireNonNull(binding, "binding");
        Objects.requireNonNull(entityType, "entityType");
        if (entityType.isBlank()) {
            throw new IllegalArgumentException("entityType must not be blank");
        }
    }
}
