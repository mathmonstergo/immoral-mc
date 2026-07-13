package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.quest.QuestNpcSource;
import java.util.Objects;

public record CitizensIntegrationHandle(
        CitizensNpcResolver resolver,
        CitizensNpcSelector selector,
        QuestNpcSource questNpcSource) {
    public CitizensIntegrationHandle {
        Objects.requireNonNull(resolver, "resolver");
        Objects.requireNonNull(selector, "selector");
        Objects.requireNonNull(questNpcSource, "questNpcSource");
    }

    public static CitizensIntegrationHandle unavailable() {
        return new CitizensIntegrationHandle(
                CitizensNpcResolver.unavailable(),
                CitizensNpcSelector.unavailable(),
                QuestNpcSource.unavailable());
    }
}
