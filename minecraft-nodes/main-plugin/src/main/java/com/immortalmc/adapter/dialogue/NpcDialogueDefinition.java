package com.immortalmc.adapter.dialogue;

import java.util.List;
import java.util.Objects;

public record NpcDialogueDefinition(
        String id,
        String title,
        String speaker,
        List<String> openingLines,
        List<String> lines,
        int lineDelayTicks,
        String sound,
        float pitch) {
    public NpcDialogueDefinition {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(title, "title");
        Objects.requireNonNull(speaker, "speaker");
        openingLines = List.copyOf(Objects.requireNonNull(openingLines, "openingLines"));
        lines = List.copyOf(Objects.requireNonNull(lines, "lines"));
        Objects.requireNonNull(sound, "sound");
        if (id.isBlank()) {
            throw new IllegalArgumentException("dialogue id must not be blank");
        }
        if (title.isBlank()) {
            throw new IllegalArgumentException("dialogue title must not be blank");
        }
        if (speaker.isBlank()) {
            throw new IllegalArgumentException("dialogue speaker must not be blank");
        }
        if (openingLines.isEmpty()) {
            throw new IllegalArgumentException("dialogue opening-lines must not be empty");
        }
        if (lines.isEmpty()) {
            throw new IllegalArgumentException("dialogue lines must not be empty");
        }
        if (lineDelayTicks <= 0) {
            throw new IllegalArgumentException("dialogue line-delay-ticks must be positive");
        }
        if (pitch <= 0.0f) {
            throw new IllegalArgumentException("dialogue pitch must be positive");
        }
        if (sound.isBlank()) {
            throw new IllegalArgumentException("dialogue sound must not be blank");
        }
    }
}
