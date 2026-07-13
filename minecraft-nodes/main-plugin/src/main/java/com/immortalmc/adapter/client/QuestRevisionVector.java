package com.immortalmc.adapter.client;

import java.util.Objects;

public record QuestRevisionVector(long player, long quest, String definitions) {
    public QuestRevisionVector {
        Objects.requireNonNull(definitions, "definitions");
    }
}
