package com.immortalmc.adapter.command;

import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public record ImmortalCommandSource(Optional<UUID> minecraftUuid) {
    public static ImmortalCommandSource console() {
        return new ImmortalCommandSource(Optional.empty());
    }

    public static ImmortalCommandSource player(UUID minecraftUuid) {
        return new ImmortalCommandSource(Optional.of(Objects.requireNonNull(minecraftUuid, "minecraftUuid")));
    }
}
