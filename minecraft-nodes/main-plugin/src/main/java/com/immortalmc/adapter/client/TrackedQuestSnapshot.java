package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;

public record TrackedQuestSnapshot(
        String questId,
        String title,
        String state,
        List<QuestObjectiveSnapshot> objectives,
        String nextActionHint) {
    public TrackedQuestSnapshot {
        Objects.requireNonNull(questId, "questId");
        Objects.requireNonNull(title, "title");
        Objects.requireNonNull(state, "state");
        objectives = List.copyOf(objectives);
        Objects.requireNonNull(nextActionHint, "nextActionHint");
    }
}
