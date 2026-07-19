package com.immortalmc.adapter.item;

import com.immortalmc.adapter.client.ItemDeliveryConfirmationSnapshot;
import com.immortalmc.adapter.client.ItemInstancesSnapshot;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

/** Game Service contract used by physical-item reconciliation. */
public interface PhysicalItemGateway {
    CompletableFuture<ItemInstancesSnapshot> fetchPendingItemDeliveries(UUID accountId);

    CompletableFuture<ItemInstancesSnapshot> fetchInventoryItems(UUID accountId);

    CompletableFuture<ItemDeliveryConfirmationSnapshot> confirmItemDelivery(
            UUID accountId,
            UUID itemInstanceId);
}
