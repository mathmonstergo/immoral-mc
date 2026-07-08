package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Function;

public record ImmortalCommandSource(
        Optional<UUID> minecraftUuid,
        Optional<EntityInteractionEntity> lookedAtEntity,
        Optional<Function<String, EntityInteractionEntity>> entitySpawner,
        Optional<Function<EntityBinding, Boolean>> entityRemover) {
    public ImmortalCommandSource {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(lookedAtEntity, "lookedAtEntity");
        Objects.requireNonNull(entitySpawner, "entitySpawner");
        Objects.requireNonNull(entityRemover, "entityRemover");
    }

    public static ImmortalCommandSource console() {
        return new ImmortalCommandSource(Optional.empty(), Optional.empty(), Optional.empty(), Optional.empty());
    }

    public static ImmortalCommandSource player(UUID minecraftUuid) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.empty(),
                Optional.empty(),
                Optional.empty());
    }

    public static ImmortalCommandSource player(UUID minecraftUuid, EntityInteractionEntity lookedAtEntity) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.of(Objects.requireNonNull(lookedAtEntity, "lookedAtEntity")),
                Optional.empty(),
                Optional.empty());
    }

    public static ImmortalCommandSource player(
            UUID minecraftUuid,
            EntityInteractionEntity lookedAtEntity,
            Function<EntityBinding, Boolean> entityRemover) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.of(Objects.requireNonNull(lookedAtEntity, "lookedAtEntity")),
                Optional.empty(),
                Optional.of(Objects.requireNonNull(entityRemover, "entityRemover")));
    }

    public static ImmortalCommandSource playerWithSpawner(
            UUID minecraftUuid,
            Function<String, EntityInteractionEntity> entitySpawner) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.empty(),
                Optional.of(Objects.requireNonNull(entitySpawner, "entitySpawner")),
                Optional.empty());
    }

    public static ImmortalCommandSource player(
            UUID minecraftUuid,
            Optional<EntityInteractionEntity> lookedAtEntity,
            Function<String, EntityInteractionEntity> entitySpawner,
            Function<EntityBinding, Boolean> entityRemover) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Objects.requireNonNull(lookedAtEntity, "lookedAtEntity"),
                Optional.of(Objects.requireNonNull(entitySpawner, "entitySpawner")),
                Optional.of(Objects.requireNonNull(entityRemover, "entityRemover")));
    }
}
