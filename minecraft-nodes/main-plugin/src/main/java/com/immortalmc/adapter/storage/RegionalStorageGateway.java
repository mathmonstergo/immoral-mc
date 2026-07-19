package com.immortalmc.adapter.storage;

import com.immortalmc.adapter.client.StorageMoveRequest;
import com.immortalmc.adapter.client.StorageMoveSnapshot;
import com.immortalmc.adapter.client.StorageSnapshot;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/** Game Service contract used by the regional storage presentation. */
public interface RegionalStorageGateway {
    CompletableFuture<StorageSnapshot> fetchStorage(UUID accountId, String areaId, int page);

    CompletableFuture<StorageMoveSnapshot> moveStorage(
            UUID accountId,
            String areaId,
            StorageMoveRequest request,
            UUID operationId);
}
