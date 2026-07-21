package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;

public record ProviderQuestSnapshot(
        String questId,
        String title,
        String description,
        String category,
        String state,
        String action,
        String dialogueKey,
        List<QuestObjectiveSnapshot> objectives,
        List<QuestRewardPreview> rewardPreviews) {
    public ProviderQuestSnapshot {
        Objects.requireNonNull(questId, "questId");
        Objects.requireNonNull(title, "title");
        Objects.requireNonNull(description, "description");
        Objects.requireNonNull(category, "category");
        Objects.requireNonNull(state, "state");
        Objects.requireNonNull(action, "action");
        objectives = List.copyOf(objectives);
        rewardPreviews = List.copyOf(rewardPreviews);
    }
}
