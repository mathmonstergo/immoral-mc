package com.immortalmc.adapter.presentation;

import java.util.List;

public interface QuestScoreboardView {
    void setQuestTitle(String value);

    void setObjectives(List<String> values);

    void setHint(String value);

    void hide();
}
