package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class QuestScoreboardRendererTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");

    @Test
    void rendersInitialModelThenUpdatesOnlyChangedLines() {
        RecordingFactory factory = new RecordingFactory();
        QuestScoreboardRenderer renderer = new QuestScoreboardRenderer(factory);

        renderer.render(PLAYER_ID, tracked(0, "前往鉴灵师处"));
        renderer.render(PLAYER_ID, tracked(0, "前往鉴灵师处"));
        renderer.render(PLAYER_ID, tracked(1, "返回老村民处"));

        assertEquals(
                List.of(
                        "quest:初入凡尘",
                        "objectives:[灵根检测  0/1]",
                        "hint:前往鉴灵师处",
                        "objectives:[灵根检测  1/1]",
                        "hint:返回老村民处"),
                factory.view.writes);
    }

    @Test
    void nullTrackedQuestAndCleanupHideExactlyOnce() {
        RecordingFactory factory = new RecordingFactory();
        QuestScoreboardRenderer renderer = new QuestScoreboardRenderer(factory);
        renderer.render(PLAYER_ID, tracked(0, "前往鉴灵师处"));

        renderer.render(PLAYER_ID, null);
        renderer.clearPlayer(PLAYER_ID);

        assertEquals(1, factory.view.hides);
    }

    @Test
    void rendersAllObjectivesAndRemovesRowsWhenTheListShrinks() {
        RecordingFactory factory = new RecordingFactory();
        QuestScoreboardRenderer renderer = new QuestScoreboardRenderer(factory);
        TrackedQuestSnapshot fourObjectives = new TrackedQuestSnapshot(
                "mixed",
                "试炼",
                "active",
                List.of(
                        new QuestObjectiveSnapshot("item", "交付", 1, 2, false),
                        new QuestObjectiveSnapshot("kill", "击杀", 3, 5, false),
                        new QuestObjectiveSnapshot("technique", "功法", 6, 7, false),
                        new QuestObjectiveSnapshot("realm", "境界", 13, 14, false)),
                "继续修炼");
        TrackedQuestSnapshot oneObjective = new TrackedQuestSnapshot(
                "mixed",
                "试炼",
                "active",
                List.of(new QuestObjectiveSnapshot("realm", "境界", 14, 14, true)),
                "返回执事处");

        renderer.render(PLAYER_ID, fourObjectives);
        renderer.render(PLAYER_ID, oneObjective);

        assertTrue(factory.view.writes.contains(
                "objectives:[交付  1/2, 击杀  3/5, 功法  6/7, 境界  13/14]"));
        assertTrue(factory.view.writes.contains("objectives:[境界  14/14]"));
    }

    private static TrackedQuestSnapshot tracked(int current, String hint) {
        return new TrackedQuestSnapshot(
                "first-steps",
                "初入凡尘",
                current == 0 ? "active" : "ready_to_turn_in",
                List.of(new QuestObjectiveSnapshot("detect-spirit-root", "灵根检测", current, 1, current == 1)),
                hint);
    }

    private static final class RecordingFactory implements QuestScoreboardRenderer.ViewFactory {
        private final RecordingView view = new RecordingView();

        @Override
        public QuestScoreboardView create(UUID playerId) {
            return view;
        }
    }

    private static final class RecordingView implements QuestScoreboardView {
        private final List<String> writes = new ArrayList<>();
        private int hides;

        @Override
        public void setQuestTitle(String value) {
            writes.add("quest:" + value);
        }

        @Override
        public void setObjectives(List<String> values) {
            writes.add("objectives:" + values);
        }

        @Override
        public void setHint(String value) {
            writes.add("hint:" + value);
        }

        @Override
        public void hide() {
            hides++;
        }
    }
}
