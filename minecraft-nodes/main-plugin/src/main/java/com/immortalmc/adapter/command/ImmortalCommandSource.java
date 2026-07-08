package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public record ImmortalCommandSource(Optional<UUID> minecraftUuid, Optional<EntityBinding> lookedAtEntity) {
    public ImmortalCommandSource {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(lookedAtEntity, "lookedAtEntity");
    }

    public static ImmortalCommandSource console() {
        return new ImmortalCommandSource(Optional.empty(), Optional.empty());
    }

    public static ImmortalCommandSource player(UUID minecraftUuid) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.empty());
    }

    public static ImmortalCommandSource player(UUID minecraftUuid, EntityBinding lookedAtEntity) {
        return new ImmortalCommandSource(
                Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")),
                Optional.of(Objects.requireNonNull(lookedAtEntity, "lookedAtEntity")));
    }
}
