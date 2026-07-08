package com.immortalmc.adapter.content;

import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public record EntityInteractionDefinition(
        String id,
        String action,
        EntityBinding binding,
        String entityType,
        boolean protectedEntity,
        boolean managedEntity,
        Map<String, String> metadata) {
    public EntityInteractionDefinition(
            String id,
            String action,
            EntityBinding binding,
            String entityType,
            boolean protectedEntity) {
        this(id, action, binding, entityType, protectedEntity, false);
    }

    public EntityInteractionDefinition(
            String id,
            String action,
            EntityBinding binding,
            String entityType,
            boolean protectedEntity,
            boolean managedEntity) {
        this(id, action, binding, entityType, protectedEntity, managedEntity, Map.of());
    }

    public EntityInteractionDefinition {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(action, "action");
        Objects.requireNonNull(binding, "binding");
        Objects.requireNonNull(entityType, "entityType");
        metadata = Map.copyOf(Objects.requireNonNull(metadata, "metadata"));
        if (id.isBlank()) {
            throw new IllegalArgumentException("id must not be blank");
        }
        if (action.isBlank()) {
            throw new IllegalArgumentException("action must not be blank");
        }
        if (entityType.isBlank()) {
            throw new IllegalArgumentException("entityType must not be blank");
        }
        for (Map.Entry<String, String> entry : metadata.entrySet()) {
            if (entry.getKey().isBlank()) {
                throw new IllegalArgumentException("metadata key must not be blank");
            }
            if (entry.getValue().isBlank()) {
                throw new IllegalArgumentException("metadata value must not be blank");
            }
        }
    }

    public Optional<String> metadataValue(String key) {
        Objects.requireNonNull(key, "key");
        return Optional.ofNullable(metadata.get(key));
    }
}
