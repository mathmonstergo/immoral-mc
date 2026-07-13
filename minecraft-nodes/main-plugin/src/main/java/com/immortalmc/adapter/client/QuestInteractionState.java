package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;
import java.util.UUID;

public record QuestInteractionState(
        int contractVersion,
        UUID accountId,
        UUID lifeId,
        QuestRevisionVector revision,
        List<QuestProviderSnapshot> providers,
        TrackedQuestSnapshot trackedQuest,
        long cacheTtlMs) {
    public QuestInteractionState {
        Objects.requireNonNull(accountId, "accountId");
        Objects.requireNonNull(lifeId, "lifeId");
        Objects.requireNonNull(revision, "revision");
        providers = List.copyOf(providers);
    }
}
