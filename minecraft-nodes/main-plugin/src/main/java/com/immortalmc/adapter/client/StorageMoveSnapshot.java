package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.UUID;

public record StorageMoveSnapshot(
        int contractVersion,
        UUID operationId,
        String moveKind,
        UUID itemInstanceId,
        StorageSnapshot snapshot) {
    public StorageMoveSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported storage move contract version");
        }
        Objects.requireNonNull(operationId, "operationId");
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        Objects.requireNonNull(snapshot, "snapshot");
        if (!"deposit".equals(moveKind) && !"withdraw".equals(moveKind) && !"move".equals(moveKind)) {
            throw new IllegalArgumentException("Unknown storage move kind");
        }
    }
}
