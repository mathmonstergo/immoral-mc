package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import java.util.Objects;

public record QuestScoreboardModel(String questTitle, String objective, String hint) {
    public QuestScoreboardModel {
        Objects.requireNonNull(questTitle, "questTitle");
        Objects.requireNonNull(objective, "objective");
        Objects.requireNonNull(hint, "hint");
    }

    public static QuestScoreboardModel from(TrackedQuestSnapshot trackedQuest) {
        Objects.requireNonNull(trackedQuest, "trackedQuest");
        String objective = "";
        if (!trackedQuest.objectives().isEmpty()) {
            QuestObjectiveSnapshot first = trackedQuest.objectives().getFirst();
            objective = first.title() + "  " + first.current() + "/" + first.required();
        }
        return new QuestScoreboardModel(
                trackedQuest.title(),
                objective,
                trackedQuest.nextActionHint());
    }
}
