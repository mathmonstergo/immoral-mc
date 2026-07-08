package com.immortalmc.adapter.content;

import java.util.Objects;

public record EntityInteractionDefinition(
        String id,
        String action,
        EntityBinding binding,
        String entityType,
        boolean protectedEntity) {
    public EntityInteractionDefinition {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(binding, "binding");
        Objects.requireNonNull(entityType, "entityType");
        if (id.isBlank()) {
            throw new IllegalArgumentException("id must not be blank");
        }
        if (action.isBlank()) {
            throw new IllegalArgumentException("action must not be blank");
        }
        if (entityType.isBlank()) {
            throw new IllegalArgumentException("entityType must not be blank");
        }
    }
}
