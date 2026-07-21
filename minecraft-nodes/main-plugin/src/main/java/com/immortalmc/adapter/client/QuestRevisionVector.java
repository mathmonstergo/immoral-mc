package com.immortalmc.adapter.client;

import java.util.Objects;

public record QuestRevisionVector(long player, long quest, long objectives, String definitions) {
    public QuestRevisionVector {
        Objects.requireNonNull(definitions, "definitions");
    }

    public boolean isOlderThan(QuestRevisionVector current) {
        Objects.requireNonNull(current, "current");
        return definitions.equals(current.definitions)
                && (player < current.player
                        || quest < current.quest
                        || objectives < current.objectives);
    }

    public boolean isSupersededBy(QuestRevisionVector authoritative) {
        Objects.requireNonNull(authoritative, "authoritative");
        return !definitions.equals(authoritative.definitions) || isOlderThan(authoritative);
    }
}
