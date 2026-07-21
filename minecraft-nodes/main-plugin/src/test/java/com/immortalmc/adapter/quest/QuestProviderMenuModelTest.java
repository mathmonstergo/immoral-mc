package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.QuestRewardPreview;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class QuestProviderMenuModelTest {
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");

    @Test
    void sortsByAuthoritativeStateAndKeepsLockedAndCompletedVisible() {
        QuestProviderMenuModel model = QuestProviderMenuModel.from(state(List.of(
                quest("completed", "completed", "talk"),
                quest("locked", "unavailable", "none"),
                quest("available", "available", "offer"),
                quest("active", "active", "remind"),
                quest("ready", "ready_to_turn_in", "turn_in"))), "old-man");

        assertEquals(
                List.of("ready", "active", "available", "locked", "completed"),
                model.quests().stream().map(QuestProviderMenuModel.QuestEntry::questId).toList());
        assertFalse(model.findQuest("locked").orElseThrow().viewable());
        assertTrue(model.findQuest("completed").orElseThrow().viewable());
        assertEquals(
                QuestProviderMenuModel.BookKind.BOOK,
                model.findQuest("available").orElseThrow().bookKind());
        assertEquals(
                QuestProviderMenuModel.BookKind.WRITTEN_BOOK,
                model.findQuest("active").orElseThrow().bookKind());
    }

    @Test
    void exposesUncappedSharedProgressAndStateSpecificActions() {
        QuestObjectiveSnapshot objective = new QuestObjectiveSnapshot(
                "iron", "item_delivery", "玄铁", "mystic_iron", 20, 15, true);
        QuestProviderMenuModel model = QuestProviderMenuModel.from(state(List.of(new ProviderQuestSnapshot(
                "ready",
                "矿洞补给",
                "收集矿洞中的玄铁。",
                "side",
                "ready_to_turn_in",
                "turn_in",
                null,
                List.of(objective),
                List.of(new QuestRewardPreview("cultivation", "unrefined_cultivation", null, null, 50))))), "old-man");

        assertEquals("玄铁 20 / 15", QuestProviderMenuModel.progressText(objective));
        assertEquals(
                QuestProviderMenuModel.PrimaryAction.TURN_IN,
                model.findQuest("ready").orElseThrow().primaryAction());
    }

    @Test
    void distinguishesLockedQuestsFromActionsOwnedByAnotherProvider() {
        QuestProviderMenuModel model = QuestProviderMenuModel.from(state(List.of(
                quest("accept-elsewhere", "available", "none"),
                quest("turn-in-elsewhere", "ready_to_turn_in", "remind"),
                quest("locked", "unavailable", "none"))), "old-man");

        assertEquals(
                QuestProviderMenuModel.PrimaryAction.DISABLED_ACCEPT_ELSEWHERE,
                model.findQuest("accept-elsewhere").orElseThrow().primaryAction());
        assertEquals(
                QuestProviderMenuModel.PrimaryAction.DISABLED_TURN_IN_ELSEWHERE,
                model.findQuest("turn-in-elsewhere").orElseThrow().primaryAction());
        assertEquals(
                QuestProviderMenuModel.PrimaryAction.DISABLED_LOCKED,
                model.findQuest("locked").orElseThrow().primaryAction());
    }

    @Test
    void definitionsChangeStartsANewMenuRevisionEpoch() {
        List<ProviderQuestSnapshot> quests = List.of(quest("available", "available", "offer"));
        QuestProviderMenuModel current = QuestProviderMenuModel.from(
                state(quests, new QuestRevisionVector(9, 9, 9, "sha256:old")),
                "old-man");
        QuestProviderMenuModel sameDefinitionsOlder = QuestProviderMenuModel.from(
                state(quests, new QuestRevisionVector(1, 1, 1, "sha256:old")),
                "old-man");
        QuestProviderMenuModel newDefinitions = QuestProviderMenuModel.from(
                state(quests, new QuestRevisionVector(1, 1, 1, "sha256:new")),
                "old-man");

        assertTrue(sameDefinitionsOlder.isOlderThan(current));
        assertFalse(newDefinitions.isOlderThan(current));
    }

    private static QuestInteractionState state(List<ProviderQuestSnapshot> quests) {
        return state(quests, new QuestRevisionVector(1, 2, 3, "sha256:definitions"));
    }

    private static QuestInteractionState state(
            List<ProviderQuestSnapshot> quests, QuestRevisionVector revision) {
        return new QuestInteractionState(
                2,
                ACCOUNT_ID,
                LIFE_ID,
                revision,
                List.of(new QuestProviderSnapshot("old-man", "state", quests, List.of(), null, null)),
                null,
                2000);
    }

    private static ProviderQuestSnapshot quest(String id, String state, String action) {
        return new ProviderQuestSnapshot(
                id,
                id,
                "description",
                "side",
                state,
                action,
                null,
                List.of(new QuestObjectiveSnapshot(
                        id + "-objective",
                        "realm_level_reached",
                        "境界",
                        null,
                        1,
                        2,
                        false)),
                List.of());
    }
}
