package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public final class QuestScoreboardRenderer {
    private final ViewFactory viewFactory;
    private final Map<UUID, RenderState> states = new HashMap<>();

    public QuestScoreboardRenderer(ViewFactory viewFactory) {
        this.viewFactory = Objects.requireNonNull(viewFactory, "viewFactory");
    }

    public void render(UUID playerId, TrackedQuestSnapshot trackedQuest) {
        Objects.requireNonNull(playerId, "playerId");
        if (trackedQuest == null) {
            clearPlayer(playerId);
            return;
        }

        QuestScoreboardModel next = QuestScoreboardModel.from(trackedQuest);
        RenderState state = states.computeIfAbsent(
                playerId,
                id -> new RenderState(viewFactory.create(id), null));
        QuestScoreboardModel previous = state.model;
        if (previous == null || !previous.questTitle().equals(next.questTitle())) {
            state.view.setQuestTitle(next.questTitle());
        }
        if (previous == null || !previous.objective().equals(next.objective())) {
            state.view.setObjective(next.objective());
        }
        if (previous == null || !previous.hint().equals(next.hint())) {
            state.view.setHint(next.hint());
        }
        state.model = next;
    }

    public void clearPlayer(UUID playerId) {
        RenderState state = states.remove(Objects.requireNonNull(playerId, "playerId"));
        if (state != null) {
            state.view.hide();
        }
    }

    public void clear() {
        List<RenderState> existing = List.copyOf(states.values());
        states.clear();
        existing.forEach(state -> state.view.hide());
    }

    @FunctionalInterface
    public interface ViewFactory {
        QuestScoreboardView create(UUID playerId);
    }

    private static final class RenderState {
        private final QuestScoreboardView view;
        private QuestScoreboardModel model;

        private RenderState(QuestScoreboardView view, QuestScoreboardModel model) {
            this.view = Objects.requireNonNull(view, "view");
            this.model = model;
        }
    }
}
