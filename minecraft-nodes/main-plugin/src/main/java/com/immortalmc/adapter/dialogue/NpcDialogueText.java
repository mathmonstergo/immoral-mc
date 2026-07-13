package com.immortalmc.adapter.dialogue;

import java.util.Objects;

public final class NpcDialogueText {
    private NpcDialogueText() {}

    public static String formatSpeakerLine(String speaker, String line) {
        return "§6" + Objects.requireNonNull(speaker, "speaker")
                + "§7: §f"
                + Objects.requireNonNull(line, "line");
    }
}
