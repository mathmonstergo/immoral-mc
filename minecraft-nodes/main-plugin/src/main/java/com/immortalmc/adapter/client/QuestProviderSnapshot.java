package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;

public record QuestProviderSnapshot(
        String providerId,
        String stateKey,
        List<ProviderQuestSnapshot> quests,
        List<String> actionableQuestIds,
        String directActionQuestId,
        ProximityBarkSnapshot proximityBark) {
    public QuestProviderSnapshot {
        Objects.requireNonNull(providerId, "providerId");
        Objects.requireNonNull(stateKey, "stateKey");
        quests = List.copyOf(quests);
        actionableQuestIds = List.copyOf(actionableQuestIds);
    }

    public record ProximityBarkSnapshot(String key, String speaker, String text, int cooldownSeconds) {
        public ProximityBarkSnapshot {
            Objects.requireNonNull(key, "key");
            Objects.requireNonNull(speaker, "speaker");
            Objects.requireNonNull(text, "text");
        }
    }
}
