package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

public interface QuestInteractionService {
    CompletableFuture<QuestInteractionState> refresh(
            UUID playerId, UUID accountId, UUID lifeId, String providerId);

    CompletableFuture<QuestMutationResult> accept(
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            String questId,
            String providerId,
            UUID operationId);

    CompletableFuture<QuestMutationResult> turnIn(
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            String questId,
            String providerId,
            UUID operationId,
            List<UUID> inventoryItemInstanceIds);
}
