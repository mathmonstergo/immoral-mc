package com.immortalmc.adapter.client;

import java.util.Objects;
import java.util.Set;

public record QuestObjectiveSnapshot(
        String objectiveId,
        String objectiveType,
        String title,
        String itemCode,
        int current,
        int required,
        boolean completed) {
    private static final Set<String> SUPPORTED_OBJECTIVE_TYPES = Set.of(
            "current_life_spirit_root_present",
            "item_delivery",
            "mythicmob_kill_count",
            "technique_layer_reached",
            "realm_level_reached");

    public QuestObjectiveSnapshot {
        Objects.requireNonNull(objectiveId, "objectiveId");
        Objects.requireNonNull(objectiveType, "objectiveType");
        Objects.requireNonNull(title, "title");
        if (!SUPPORTED_OBJECTIVE_TYPES.contains(objectiveType)) {
            throw new IllegalArgumentException("Unsupported quest objective type: " + objectiveType);
        }
        if ("item_delivery".equals(objectiveType)) {
            if (itemCode == null || itemCode.isBlank()) {
                throw new IllegalArgumentException("Item-delivery objective requires itemCode");
            }
        } else if (itemCode != null) {
            throw new IllegalArgumentException("Only item-delivery objective can include itemCode");
        }
        if (current < 0 || required <= 0) {
            throw new IllegalArgumentException("Quest objective quantities are invalid");
        }
    }
}
