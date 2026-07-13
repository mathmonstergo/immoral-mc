package com.immortalmc.adapter.client;

import java.util.Objects;

public record QuestObjectiveSnapshot(
        String objectiveId, String title, int current, int required, boolean completed) {
    public QuestObjectiveSnapshot {
        Objects.requireNonNull(objectiveId, "objectiveId");
        Objects.requireNonNull(title, "title");
    }
}
