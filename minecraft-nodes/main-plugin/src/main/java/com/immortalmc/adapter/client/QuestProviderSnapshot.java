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
            key = requireNonBlank(key, "key");
            speaker = requireNonBlank(speaker, "speaker");
            text = requireNonBlank(text, "text");
            if (cooldownSeconds < 1 || cooldownSeconds > 86_400) {
                throw new IllegalArgumentException("cooldownSeconds must be between 1 and 86400");
            }
        }

        private static String requireNonBlank(String value, String name) {
            Objects.requireNonNull(value, name);
            if (value.isBlank() || !value.equals(value.strip())) {
                throw new IllegalArgumentException(name + " must be trimmed and non-blank");
            }
            return value;
        }
    }
}
