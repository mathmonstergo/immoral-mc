package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.quest.QuestProviderMenuModel;
import java.util.List;
import java.util.Objects;

public record QuestScoreboardModel(String questTitle, List<String> objectives, String hint) {
    public QuestScoreboardModel {
        Objects.requireNonNull(questTitle, "questTitle");
        objectives = List.copyOf(objectives);
        Objects.requireNonNull(hint, "hint");
    }

    public static QuestScoreboardModel from(TrackedQuestSnapshot trackedQuest) {
        Objects.requireNonNull(trackedQuest, "trackedQuest");
        List<String> objectives = trackedQuest.objectives().stream()
                .map(QuestProviderMenuModel::progressText)
                .toList();
        return new QuestScoreboardModel(
                trackedQuest.title(),
                objectives,
                trackedQuest.nextActionHint());
    }
}
