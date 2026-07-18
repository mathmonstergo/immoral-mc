package com.immortalmc.adapter.client;

import java.util.Objects;

public record QuestRevisionVector(long player, long quest, long objectives, String definitions) {
    public QuestRevisionVector {
        Objects.requireNonNull(definitions, "definitions");
    }
}
