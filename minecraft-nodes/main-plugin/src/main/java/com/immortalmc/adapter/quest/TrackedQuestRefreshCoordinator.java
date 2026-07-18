package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BiConsumer;

public final class TrackedQuestRefreshCoordinator {
    private final Object lock = new Object();
    private final Gateway gateway;
    private final PlayerSessionCache sessions;
    private final MainThreadDispatcher dispatcher;
    private final BiConsumer<UUID, TrackedQuestSnapshot> renderer;
    private final AdapterLogger logger;
    private final Map<UUID, RefreshState> states = new HashMap<>();
    private final AtomicLong generationSequence = new AtomicLong();

    public TrackedQuestRefreshCoordinator(
            GameServiceClient client,
            PlayerSessionCache sessions,
            MainThreadDispatcher dispatcher,
            BiConsumer<UUID, TrackedQuestSnapshot> renderer,
            AdapterLogger logger) {
        this(
                accountId -> client.fetchQuestInteractionState(accountId, List.of()),
                sessions,
                dispatcher,
                renderer,
                logger);
    }

    TrackedQuestRefreshCoordinator(
            Gateway gateway,
            PlayerSessionCache sessions,
            MainThreadDispatcher dispatcher,
            BiConsumer<UUID, TrackedQuestSnapshot> renderer,
            AdapterLogger logger) {
        this.gateway = Objects.requireNonNull(gateway, "gateway");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        this.dispatcher = Objects.requireNonNull(dispatcher, "dispatcher");
        this.renderer = Objects.requireNonNull(renderer, "renderer");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void refresh(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        PlayerLoginResult session = sessions.findByMinecraftUuid(playerId).orElse(null);
        if (session == null) {
            return;
        }
        UUID accountId = session.account().accountId();
        UUID lifeId = session.currentLife().lifeId();
        long generation;
        boolean clearProjection = false;
        synchronized (lock) {
            RefreshState state = states.get(playerId);
            if (state == null) {
                state = new RefreshState(accountId, lifeId);
                states.put(playerId, state);
            } else if (!state.matches(accountId, lifeId)) {
                state = new RefreshState(accountId, lifeId);
                states.put(playerId, state);
                clearProjection = true;
            }
            if (state.inFlight) {
                state.dirty = true;
                return;
            }
            state.inFlight = true;
            state.dirty = false;
            generation = generationSequence.incrementAndGet();
            state.generation = generation;
        }

        if (clearProjection) {
            dispatch(
                    () -> renderer.accept(playerId, null),
                    playerId,
                    "quest_tracked_life_clear_dispatch_failed");
        }
        CompletableFuture<QuestInteractionState> request;
        try {
            request = gateway.fetch(accountId);
        } catch (Throwable error) {
            request = CompletableFuture.failedFuture(error);
        }
        request.whenComplete((response, error) -> dispatchRefreshCompletion(
                playerId,
                accountId,
                lifeId,
                generation,
                response,
                error));
    }

    public void publish(UUID playerId, QuestInteractionState state) {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(state, "state");
        dispatch(
                () -> applyPublishedState(playerId, state),
                playerId,
                "quest_tracked_publish_dispatch_failed");
    }

    public void clearPlayer(UUID playerId) {
        synchronized (lock) {
            states.remove(Objects.requireNonNull(playerId, "playerId"));
        }
    }

    public void clear() {
        synchronized (lock) {
            states.clear();
        }
    }

    private void finishRefresh(
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            long generation,
            QuestInteractionState response,
            Throwable error) {
        boolean trailing;
        boolean publish = false;
        TrackedQuestSnapshot trackedQuest = null;
        String failure = null;
        synchronized (lock) {
            RefreshState state = states.get(playerId);
            if (state == null
                    || !state.matches(accountId, lifeId)
                    || state.generation != generation) {
                return;
            }
            state.inFlight = false;
            PlayerLoginResult current = sessions.findByMinecraftUuid(playerId).orElse(null);
            if (error != null) {
                failure = message(error);
            } else if (!matches(current, accountId, lifeId)
                    || response == null
                    || !response.accountId().equals(accountId)
                    || !response.lifeId().equals(lifeId)) {
                failure = "stale account or life response";
            } else if (!isOlder(response.revision(), state.lastRevision)) {
                state.lastRevision = response.revision();
                trackedQuest = response.trackedQuest();
                publish = true;
            }
            trailing = state.dirty;
            state.dirty = false;
        }
        if (failure != null) {
            logger.warn("quest_tracked_refresh_failed minecraft_uuid=" + playerId + " reason=" + failure);
        } else if (publish) {
            renderer.accept(playerId, trackedQuest);
        }
        if (trailing) {
            refresh(playerId);
        }
    }

    private void applyPublishedState(UUID playerId, QuestInteractionState response) {
        PlayerLoginResult session = sessions.findByMinecraftUuid(playerId).orElse(null);
        if (session == null
                || !response.accountId().equals(session.account().accountId())
                || !response.lifeId().equals(session.currentLife().lifeId())) {
            return;
        }
        synchronized (lock) {
            RefreshState state = states.get(playerId);
            if (state == null
                    || !state.matches(response.accountId(), response.lifeId())) {
                state = new RefreshState(response.accountId(), response.lifeId());
                states.put(playerId, state);
            }
            if (isOlder(response.revision(), state.lastRevision)) {
                return;
            }
            state.lastRevision = response.revision();
        }
        renderer.accept(playerId, response.trackedQuest());
    }

    private void dispatchRefreshCompletion(
            UUID playerId,
            UUID accountId,
            UUID lifeId,
            long generation,
            QuestInteractionState response,
            Throwable error) {
        try {
            dispatcher.dispatch(
                    () -> finishRefresh(
                            playerId,
                            accountId,
                            lifeId,
                            generation,
                            response,
                            error));
        } catch (RuntimeException dispatchError) {
            synchronized (lock) {
                RefreshState state = states.get(playerId);
                if (state != null
                        && state.matches(accountId, lifeId)
                        && state.generation == generation) {
                    state.inFlight = false;
                }
            }
            logger.warn(
                    "quest_tracked_refresh_dispatch_failed minecraft_uuid=" + playerId,
                    dispatchError);
        }
    }

    private void dispatch(Runnable action, UUID playerId, String event) {
        try {
            dispatcher.dispatch(action);
        } catch (RuntimeException error) {
            logger.warn(event + " minecraft_uuid=" + playerId, error);
        }
    }

    private static boolean matches(PlayerLoginResult session, UUID accountId, UUID lifeId) {
        return session != null
                && session.account().accountId().equals(accountId)
                && session.currentLife().lifeId().equals(lifeId);
    }

    private static boolean isOlder(QuestRevisionVector candidate, QuestRevisionVector current) {
        return current != null
                && (candidate.player() < current.player()
                        || candidate.quest() < current.quest()
                        || candidate.objectives() < current.objectives());
    }

    private static String message(Throwable error) {
        Throwable current = error;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        return current.getMessage() == null ? current.getClass().getSimpleName() : current.getMessage();
    }

    @FunctionalInterface
    interface Gateway {
        CompletableFuture<QuestInteractionState> fetch(UUID accountId);
    }

    @FunctionalInterface
    public interface MainThreadDispatcher {
        void dispatch(Runnable action);
    }

    private static final class RefreshState {
        private final UUID accountId;
        private final UUID lifeId;
        private long generation;
        private boolean inFlight;
        private boolean dirty;
        private QuestRevisionVector lastRevision;

        private RefreshState(UUID accountId, UUID lifeId) {
            this.accountId = accountId;
            this.lifeId = lifeId;
        }

        private boolean matches(UUID expectedAccountId, UUID expectedLifeId) {
            return accountId.equals(expectedAccountId) && lifeId.equals(expectedLifeId);
        }
    }
}
