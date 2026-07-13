package com.immortalmc.adapter.quest;

import java.util.List;

@FunctionalInterface
public interface QuestNpcSource {
    List<QuestNpcPosition> snapshot();

    static QuestNpcSource unavailable() {
        return List::of;
    }
}
