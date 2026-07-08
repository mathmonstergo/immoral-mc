package com.immortalmc.adapter.dialogue;

@FunctionalInterface
public interface NpcDialogueScheduler {
    void runLater(int delayTicks, Runnable task);

    static NpcDialogueScheduler immediate() {
        return (delayTicks, task) -> task.run();
    }
}
