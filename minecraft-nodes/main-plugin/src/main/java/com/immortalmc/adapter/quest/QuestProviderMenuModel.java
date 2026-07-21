package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestObjectiveSnapshot;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.QuestRewardPreview;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

/** Pure quest-provider menu projection. It contains no Bukkit inventory state. */
public final class QuestProviderMenuModel {
    public static final int QUESTS_PER_PAGE = 45;

    private static final Map<String, Integer> STATE_RANK = Map.of(
            "ready_to_turn_in", 0,
            "active", 1,
            "available", 2,
            "unavailable", 3,
            "completed", 4);

    private final UUID accountId;
    private final UUID lifeId;
    private final QuestRevisionVector revision;
    private final String providerId;
    private final List<QuestEntry> quests;
    private final Map<String, QuestEntry> questsById;

    private QuestProviderMenuModel(
            UUID accountId,
            UUID lifeId,
            QuestRevisionVector revision,
            String providerId,
            List<QuestEntry> quests) {
        this.accountId = Objects.requireNonNull(accountId, "accountId");
        this.lifeId = Objects.requireNonNull(lifeId, "lifeId");
        this.revision = Objects.requireNonNull(revision, "revision");
        this.providerId = requireText(providerId, "providerId");
        this.quests = List.copyOf(quests);
        Map<String, QuestEntry> indexed = new LinkedHashMap<>();
        for (QuestEntry quest : quests) {
            if (indexed.put(quest.questId(), quest) != null) {
                throw new IllegalArgumentException("Duplicate quest id in provider projection: " + quest.questId());
            }
        }
        questsById = Map.copyOf(indexed);
    }

    public static QuestProviderMenuModel from(QuestInteractionState state, String providerId) {
        Objects.requireNonNull(state, "state");
        QuestProviderSnapshot provider = state.providers().stream()
                .filter(candidate -> candidate.providerId().equals(providerId))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Quest provider is absent from interaction state"));
        List<QuestEntry> quests = provider.quests().stream()
                .map(QuestEntry::from)
                .sorted(Comparator.comparingInt(QuestEntry::stateRank))
                .toList();
        return new QuestProviderMenuModel(
                state.accountId(), state.lifeId(), state.revision(), provider.providerId(), quests);
    }

    public UUID accountId() {
        return accountId;
    }

    public UUID lifeId() {
        return lifeId;
    }

    public QuestRevisionVector revision() {
        return revision;
    }

    public String providerId() {
        return providerId;
    }

    public List<QuestEntry> quests() {
        return quests;
    }

    public Optional<QuestEntry> findQuest(String questId) {
        return Optional.ofNullable(questsById.get(Objects.requireNonNull(questId, "questId")));
    }

    public int pageCount() {
        return Math.max(1, (quests.size() + QUESTS_PER_PAGE - 1) / QUESTS_PER_PAGE);
    }

    public List<QuestEntry> page(int page) {
        if (page < 1 || page > pageCount()) {
            throw new IllegalArgumentException("Quest page is outside the available range");
        }
        int start = (page - 1) * QUESTS_PER_PAGE;
        int end = Math.min(start + QUESTS_PER_PAGE, quests.size());
        return quests.subList(start, end);
    }

    public boolean isOlderThan(QuestProviderMenuModel current) {
        Objects.requireNonNull(current, "current");
        return revision.isOlderThan(current.revision);
    }

    public static String progressText(QuestObjectiveSnapshot objective) {
        Objects.requireNonNull(objective, "objective");
        return objective.title() + " " + objective.current() + " / " + objective.required();
    }

    public enum BookKind {
        BOOK,
        WRITTEN_BOOK
    }

    public enum PrimaryAction {
        ACCEPT,
        TURN_IN,
        DISABLED_ACTIVE,
        DISABLED_ACCEPT_ELSEWHERE,
        DISABLED_TURN_IN_ELSEWHERE,
        DISABLED_LOCKED,
        DISABLED_COMPLETED
    }

    public record QuestEntry(
            String questId,
            String title,
            String description,
            String category,
            String state,
            String action,
            String dialogueKey,
            List<QuestObjectiveSnapshot> objectives,
            List<QuestRewardPreview> rewardPreviews) {
        public QuestEntry {
            questId = requireText(questId, "questId");
            title = requireText(title, "title");
            Objects.requireNonNull(description, "description");
            category = requireText(category, "category");
            state = requireText(state, "state");
            action = requireText(action, "action");
            if (!STATE_RANK.containsKey(state)) {
                throw new IllegalArgumentException("Unknown quest state: " + state);
            }
            objectives = List.copyOf(objectives);
            rewardPreviews = List.copyOf(rewardPreviews);
        }

        private static QuestEntry from(ProviderQuestSnapshot quest) {
            return new QuestEntry(
                    quest.questId(),
                    quest.title(),
                    quest.description(),
                    quest.category(),
                    quest.state(),
                    quest.action(),
                    quest.dialogueKey(),
                    quest.objectives(),
                    quest.rewardPreviews());
        }

        int stateRank() {
            return STATE_RANK.get(state);
        }

        public boolean viewable() {
            return !"unavailable".equals(state);
        }

        public BookKind bookKind() {
            return switch (state) {
                case "available", "unavailable" -> BookKind.BOOK;
                case "ready_to_turn_in", "active", "completed" -> BookKind.WRITTEN_BOOK;
                default -> throw new IllegalStateException("Unknown quest state: " + state);
            };
        }

        public PrimaryAction primaryAction() {
            if ("available".equals(state) && "offer".equals(action)) {
                return PrimaryAction.ACCEPT;
            }
            if ("ready_to_turn_in".equals(state) && "turn_in".equals(action)) {
                return PrimaryAction.TURN_IN;
            }
            return switch (state) {
                case "active" -> PrimaryAction.DISABLED_ACTIVE;
                case "available" -> PrimaryAction.DISABLED_ACCEPT_ELSEWHERE;
                case "ready_to_turn_in" -> PrimaryAction.DISABLED_TURN_IN_ELSEWHERE;
                case "unavailable" -> PrimaryAction.DISABLED_LOCKED;
                case "completed" -> PrimaryAction.DISABLED_COMPLETED;
                default -> throw new IllegalStateException("Unknown quest state: " + state);
            };
        }
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return value;
    }
}
