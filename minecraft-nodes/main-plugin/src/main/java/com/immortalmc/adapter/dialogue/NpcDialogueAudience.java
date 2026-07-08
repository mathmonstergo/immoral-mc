package com.immortalmc.adapter.dialogue;

public interface NpcDialogueAudience {
    void sendMessage(String message);

    void playSound(String sound, float volume, float pitch);
}
