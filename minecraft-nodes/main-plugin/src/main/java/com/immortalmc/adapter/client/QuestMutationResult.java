package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record QuestMutationResult(
        UUID operationId,
        boolean changed,
        ProviderQuestSnapshot quest,
        QuestInteractionState interactionState,
        List<QuestRewardSnapshot> rewards,
        List<UUID> consumedItemInstanceIds) {
    public QuestMutationResult {
        Objects.requireNonNull(operationId, "operationId");
        Objects.requireNonNull(quest, "quest");
        Objects.requireNonNull(interactionState, "interactionState");
        rewards = List.copyOf(Objects.requireNonNull(rewards, "rewards"));
        consumedItemInstanceIds = List.copyOf(
                Objects.requireNonNull(consumedItemInstanceIds, "consumedItemInstanceIds"));
    }
}
