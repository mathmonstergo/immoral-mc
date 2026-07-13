package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.UUID;

public record QuestMutationResult(
        UUID operationId, boolean changed, ProviderQuestSnapshot quest, QuestInteractionState interactionState) {
    public QuestMutationResult {
        Objects.requireNonNull(operationId, "operationId");
        Objects.requireNonNull(quest, "quest");
        Objects.requireNonNull(interactionState, "interactionState");
    }
}
