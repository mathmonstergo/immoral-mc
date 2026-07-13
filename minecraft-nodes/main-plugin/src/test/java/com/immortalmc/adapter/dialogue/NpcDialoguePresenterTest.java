package com.immortalmc.adapter.dialogue;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class NpcDialoguePresenterTest {
    @Test
    void sendsTallOpeningBlockThenSchedulesNpcLinesWithVillagerPitchVariation() {
        RecordingScheduler scheduler = new RecordingScheduler();
        NpcDialoguePresenter presenter = new NpcDialoguePresenter(scheduler);
        RecordingAudience audience = new RecordingAudience();
        NpcDialogueDefinition dialogue = new NpcDialogueDefinition(
                "old-man",
                "初入凡尘",
                "老村民",
                List.of("§6§l任务开始", "§e初入凡尘"),
                List.of("年轻人，你身上有一股未定的气。", "去村外的灵石旁看看，也许能照出你的根骨。"),
                30,
                "entity.villager.ambient",
                1.0f);

        presenter.play(dialogue, audience);

        assertEquals(10, audience.messages().size());
        assertTrue(audience.messages().contains("§6§l任务开始"));
        assertTrue(audience.messages().contains("§e初入凡尘"));
        assertEquals(List.of(30, 60), scheduler.delays());

        scheduler.runAll();

        assertEquals(
                List.of(
                        "§6老村民§7: §f年轻人，你身上有一股未定的气。",
                        "§6老村民§7: §f去村外的灵石旁看看，也许能照出你的根骨。"),
                audience.messages().subList(10, 12));
        assertEquals(List.of("entity.villager.ambient", "entity.villager.ambient"), audience.sounds());
        assertEquals(2, audience.pitches().size());
        assertNotEquals(audience.pitches().get(0), audience.pitches().get(1));
    }

    @Test
    void sessionAwarePlaybackSkipsCancelledLinesAndCompletion() {
        RecordingScheduler scheduler = new RecordingScheduler();
        NpcDialoguePresenter presenter = new NpcDialoguePresenter(scheduler);
        RecordingAudience audience = new RecordingAudience();
        AtomicBoolean active = new AtomicBoolean(true);
        AtomicInteger completions = new AtomicInteger();
        NpcDialogueDefinition dialogue = new NpcDialogueDefinition(
                "offer",
                "Offer",
                "老村民",
                List.of("opening"),
                List.of("first", "second"),
                10,
                "entity.villager.ambient",
                1.0f);

        presenter.play(dialogue, audience, active::get, completions::incrementAndGet);
        active.set(false);
        scheduler.runAll();

        assertEquals(10, audience.messages().size());
        assertTrue(audience.sounds().isEmpty());
        assertEquals(0, completions.get());
    }

    private static final class RecordingScheduler implements NpcDialogueScheduler {
        private final List<ScheduledTask> tasks = new ArrayList<>();

        @Override
        public void runLater(int delayTicks, Runnable task) {
            tasks.add(new ScheduledTask(delayTicks, task));
        }

        List<Integer> delays() {
            return tasks.stream().map(ScheduledTask::delayTicks).toList();
        }

        void runAll() {
            tasks.forEach(task -> task.runnable().run());
        }
    }

    private static final class RecordingAudience implements NpcDialogueAudience {
        private final List<String> messages = new ArrayList<>();
        private final List<String> sounds = new ArrayList<>();
        private final List<Float> pitches = new ArrayList<>();

        @Override
        public void sendMessage(String message) {
            messages.add(message);
        }

        @Override
        public void playSound(String sound, float volume, float pitch) {
            sounds.add(sound);
            pitches.add(pitch);
        }

        List<String> messages() {
            return List.copyOf(messages);
        }

        List<String> sounds() {
            return List.copyOf(sounds);
        }

        List<Float> pitches() {
            return List.copyOf(pitches);
        }
    }

    private record ScheduledTask(int delayTicks, Runnable runnable) {}
}
