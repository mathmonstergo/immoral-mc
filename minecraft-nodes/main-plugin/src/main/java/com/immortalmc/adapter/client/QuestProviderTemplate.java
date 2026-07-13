package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;

public record QuestProviderTemplate(
        String providerId,
        String displayName,
        List<String> mainQuestIds,
        List<String> sideQuestIds) {
    public QuestProviderTemplate {
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(displayName, "displayName");
        mainQuestIds = List.copyOf(Objects.requireNonNull(mainQuestIds, "mainQuestIds"));
        sideQuestIds = List.copyOf(Objects.requireNonNull(sideQuestIds, "sideQuestIds"));
        if (providerId.isBlank()) {
            throw new IllegalArgumentException("providerId must not be blank");
        }
        if (displayName.isBlank()) {
            throw new IllegalArgumentException("displayName must not be blank");
        }
    }
}
