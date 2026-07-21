package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class QuestProviderInventoryHolderTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");

    @Test
    void keepsIdentityRejectsOlderProjectionAndRoutesOnlyViewableSlots() {
        QuestProviderInventoryHolder holder = holder();
        assertTrue(holder.update(model(2, "available", "offer")));
        holder.bindQuestSlot(0, "quest");
        assertEquals("quest", holder.questIdAt(0).orElseThrow());

        assertFalse(holder.update(model(1, "available", "offer")));
        holder.showDetail("quest");
        assertEquals(QuestProviderInventoryHolder.View.DETAIL, holder.view());
        holder.showList();
        assertTrue(holder.selectedQuestId().isEmpty());
        assertThrows(IllegalArgumentException.class, () -> holder.bindQuestSlot(45, "quest"));
    }

    @Test
    void serializesOneOperationAtATime() {
        QuestProviderInventoryHolder holder = holder();
        assertTrue(holder.beginOperation());
        assertFalse(holder.beginOperation());
        holder.finishOperation();
        assertTrue(holder.beginOperation());
    }

    private static QuestProviderInventoryHolder holder() {
        return new QuestProviderInventoryHolder(
                UUID.randomUUID(), PLAYER_ID, ACCOUNT_ID, LIFE_ID,
                "old-man-interaction", NPC_ID, "old-man");
    }

    private static QuestProviderMenuModel model(long objectiveRevision, String state, String action) {
        ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                "quest", "任务", "说明", "side", state, action, null,
                List.of(new QuestObjectiveSnapshot(
                        "realm", "realm_level_reached", "境界", null, 1, 2, false)),
                List.of());
        return QuestProviderMenuModel.from(new QuestInteractionState(
                2,
                ACCOUNT_ID,
                LIFE_ID,
                new QuestRevisionVector(1, 1, objectiveRevision, "sha256:definitions"),
                List.of(new QuestProviderSnapshot(
                        "old-man", "quest:" + state, List.of(quest), List.of("quest"), "quest", null)),
                null,
                2000), "old-man");
    }
}
