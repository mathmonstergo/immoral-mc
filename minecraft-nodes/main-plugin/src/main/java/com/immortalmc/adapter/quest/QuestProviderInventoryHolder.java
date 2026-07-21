package com.immortalmc.adapter.quest;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.jetbrains.annotations.NotNull;

public final class QuestProviderInventoryHolder implements InventoryHolder {
    public enum View {
        LIST,
        DETAIL
    }

    private final UUID generation;
    private final UUID playerId;
    private final UUID accountId;
    private final UUID lifeId;
    private final String interactionId;
    private final UUID npcId;
    private final String providerId;
    private QuestProviderMenuModel model;
    private View view = View.LIST;
    private int page = 1;
    private String selectedQuestId;
    private boolean busy;
    private final Map<Integer, String> questIdsBySlot = new HashMap<>();
    private Inventory inventory;

    public QuestProviderInventoryHolder(
            UUID generation,
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            String interactionId,
            UUID npcId,
            String providerId) {
        this.generation = Objects.requireNonNull(generation, "generation");
        this.playerId = Objects.requireNonNull(playerId, "playerId");
        this.accountId = Objects.requireNonNull(accountId, "accountId");
        this.lifeId = Objects.requireNonNull(lifeId, "lifeId");
        this.interactionId = requireText(interactionId, "interactionId");
        this.npcId = Objects.requireNonNull(npcId, "npcId");
        this.providerId = requireText(providerId, "providerId");
    }

    public UUID generation() {
        return generation;
    }

    public UUID playerId() {
        return playerId;
    }

    public UUID accountId() {
        return accountId;
    }

    public UUID lifeId() {
        return lifeId;
    }

    public String interactionId() {
        return interactionId;
    }

    public UUID npcId() {
        return npcId;
    }

    public String providerId() {
        return providerId;
    }

    public QuestProviderMenuModel model() {
        if (model == null) {
            throw new IllegalStateException("Quest provider model has not been loaded");
        }
        return model;
    }

    public boolean loaded() {
        return model != null;
    }

    public boolean update(QuestProviderMenuModel candidate) {
        Objects.requireNonNull(candidate, "candidate");
        if (!accountId.equals(candidate.accountId())
                || !lifeId.equals(candidate.lifeId())
                || !providerId.equals(candidate.providerId())) {
            throw new IllegalArgumentException("Quest provider model identity does not match holder");
        }
        if (model != null && candidate.isOlderThan(model)) {
            return false;
        }
        model = candidate;
        page = Math.min(page, candidate.pageCount());
        if (selectedQuestId != null && candidate.findQuest(selectedQuestId).isEmpty()) {
            showList();
        }
        return true;
    }

    public View view() {
        return view;
    }

    public int page() {
        return page;
    }

    public void showList() {
        view = View.LIST;
        selectedQuestId = null;
        questIdsBySlot.clear();
    }

    public void showDetail(String questId) {
        QuestProviderMenuModel.QuestEntry quest = model().findQuest(questId)
                .orElseThrow(() -> new IllegalArgumentException("Unknown quest id"));
        if (!quest.viewable()) {
            throw new IllegalArgumentException("Unavailable quest cannot be opened");
        }
        view = View.DETAIL;
        selectedQuestId = questId;
        questIdsBySlot.clear();
    }

    public Optional<String> selectedQuestId() {
        return Optional.ofNullable(selectedQuestId);
    }

    public void setPage(int page) {
        if (view != View.LIST || page < 1 || page > model().pageCount()) {
            throw new IllegalArgumentException("Quest list page is invalid");
        }
        this.page = page;
        questIdsBySlot.clear();
    }

    public void bindQuestSlot(int slot, String questId) {
        if (slot < 0 || slot >= QuestProviderMenuModel.QUESTS_PER_PAGE) {
            throw new IllegalArgumentException("Quest slot must be in the content area");
        }
        QuestProviderMenuModel.QuestEntry quest = model().findQuest(questId)
                .orElseThrow(() -> new IllegalArgumentException("Unknown quest id"));
        if (!quest.viewable()) {
            throw new IllegalArgumentException("Unavailable quest cannot be bound as clickable");
        }
        questIdsBySlot.put(slot, questId);
    }

    public Optional<String> questIdAt(int slot) {
        return Optional.ofNullable(questIdsBySlot.get(slot));
    }

    public void clearQuestSlots() {
        questIdsBySlot.clear();
    }

    public boolean busy() {
        return busy;
    }

    public boolean beginOperation() {
        if (busy) {
            return false;
        }
        busy = true;
        return true;
    }

    public void finishOperation() {
        busy = false;
    }

    public void attach(Inventory inventory) {
        this.inventory = Objects.requireNonNull(inventory, "inventory");
    }

    @Override
    public @NotNull Inventory getInventory() {
        if (inventory == null) {
            throw new IllegalStateException("Inventory has not been attached");
        }
        return inventory;
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return value;
    }
}
