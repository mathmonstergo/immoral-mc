package com.immortalmc.adapter.outbox;

import com.immortalmc.adapter.client.CombatKillBatchResponse;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import java.util.List;
import java.util.concurrent.CompletableFuture;

@FunctionalInterface
public interface CombatBatchSender {
    CompletableFuture<CombatKillBatchResponse> send(List<CombatKillEventRequest> requests);
}
