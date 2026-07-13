package com.immortalmc.adapter.dialogue;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.function.BooleanSupplier;

public final class NpcDialoguePresenter {
    private static final int OPENING_BLOCK_HEIGHT = 10;
    private static final float[] PITCH_OFFSETS = {-0.08f, 0.0f, 0.06f, -0.03f, 0.08f};

    private final NpcDialogueScheduler scheduler;

    public NpcDialoguePresenter(NpcDialogueScheduler scheduler) {
        this.scheduler = Objects.requireNonNull(scheduler, "scheduler");
    }

    public void play(NpcDialogueDefinition dialogue, NpcDialogueAudience audience) {
        playInternal(dialogue, audience, () -> true, null);
    }

    public void play(
            NpcDialogueDefinition dialogue,
            NpcDialogueAudience audience,
            BooleanSupplier sessionActive,
            Runnable onComplete) {
        Objects.requireNonNull(onComplete, "onComplete");
        playInternal(dialogue, audience, sessionActive, onComplete);
    }

    private void playInternal(
            NpcDialogueDefinition dialogue,
            NpcDialogueAudience audience,
            BooleanSupplier sessionActive,
            Runnable onComplete) {
        Objects.requireNonNull(dialogue, "dialogue");
        Objects.requireNonNull(audience, "audience");
        Objects.requireNonNull(sessionActive, "sessionActive");

        for (String line : openingBlock(dialogue)) {
            audience.sendMessage(line);
        }
        for (int index = 0; index < dialogue.lines().size(); index++) {
            int lineIndex = index;
            String line = dialogue.lines().get(index);
            scheduler.runLater(dialogue.lineDelayTicks() * (index + 1), () -> {
                if (!sessionActive.getAsBoolean()) {
                    return;
                }
                audience.sendMessage(formatNpcLine(dialogue.speaker(), line));
                audience.playSound(dialogue.sound(), 1.0f, pitchFor(dialogue.pitch(), lineIndex));
            });
        }
        if (onComplete != null) {
            scheduler.runLater(dialogue.lineDelayTicks() * dialogue.lines().size(), () -> {
                if (sessionActive.getAsBoolean()) {
                    onComplete.run();
                }
            });
        }
    }

    private static List<String> openingBlock(NpcDialogueDefinition dialogue) {
        List<String> block = new ArrayList<>();
        block.add("§8§m                                                    ");
        block.addAll(dialogue.openingLines());
        while (block.size() < OPENING_BLOCK_HEIGHT - 1) {
            block.add("§8 ");
        }
        block.add("§8§m                                                    ");
        return List.copyOf(block);
    }

    private static String formatNpcLine(String speaker, String line) {
        return "§6" + speaker + "§7: §f" + line;
    }

    private static float pitchFor(float basePitch, int lineIndex) {
        float pitch = basePitch + PITCH_OFFSETS[lineIndex % PITCH_OFFSETS.length];
        return Math.max(0.5f, Math.min(2.0f, pitch));
    }
}
