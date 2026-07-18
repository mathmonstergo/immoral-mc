package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class TrackedQuestRefreshCoordinatorTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000401");
    private static final UUID ACCOUNT_ID = UUID.fromString("00000000-0000-0000-0000-000000000402");
    private static final UUID LIFE_ID = UUID.fromString("00000000-0000-0000-0000-000000000403");

    @Test
    void coalescesConcurrentTriggersAndRunsOneTrailingRefresh() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.refresh(PLAYER_ID);
        coordinator.refresh(PLAYER_ID);
        coordinator.refresh(PLAYER_ID);
        assertEquals(1, gateway.requests.size());

        gateway.requests.getFirst().complete(state(LIFE_ID, 1, "first"));
        assertEquals(2, gateway.requests.size());
        gateway.requests.get(1).complete(state(LIFE_ID, 2, "second"));

        assertEquals(List.of("first", "second"), rendered);
    }

    @Test
    void staleLifeResponseIsDropped() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.refresh(PLAYER_ID);
        sessions.store(login(UUID.fromString("00000000-0000-0000-0000-000000000499")));
        gateway.requests.getFirst().complete(state(LIFE_ID, 1, "stale"));

        assertTrue(rendered.isEmpty());
    }

    @Test
    void publishedMutationInvalidatesOlderInFlightRefresh() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.refresh(PLAYER_ID);
        coordinator.publish(PLAYER_ID, state(LIFE_ID, 2, "mutation"));
        gateway.requests.getFirst().complete(state(LIFE_ID, 1, "old-refresh"));

        assertEquals(List.of("mutation"), rendered);
    }

    @Test
    void olderPublishedStateDoesNotInvalidateNewerInFlightRefresh() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.publish(PLAYER_ID, state(LIFE_ID, 1, "confirmed"));
        coordinator.refresh(PLAYER_ID);
        coordinator.publish(PLAYER_ID, state(LIFE_ID, 1, "equal-publish"));
        gateway.requests.getFirst().complete(state(LIFE_ID, 2, "newer-refresh"));

        assertEquals(List.of("confirmed", "equal-publish", "newer-refresh"), rendered);
    }

    @Test
    void clearPlayerInvalidatesLateCompletion() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.refresh(PLAYER_ID);
        coordinator.clearPlayer(PLAYER_ID);
        gateway.requests.getFirst().complete(state(LIFE_ID, 1, "late"));

        assertTrue(rendered.isEmpty());
    }

    @Test
    void oldCompletionCannotMatchSameLifeStateAfterClearAndReconnect() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.refresh(PLAYER_ID);
        coordinator.clearPlayer(PLAYER_ID);
        sessions.remove(PLAYER_ID);
        sessions.store(login(LIFE_ID));
        coordinator.refresh(PLAYER_ID);

        gateway.requests.get(1).complete(state(LIFE_ID, 2, "new-session"));
        gateway.requests.getFirst().complete(state(LIFE_ID, 99, "old-session"));

        assertEquals(List.of("new-session"), rendered);
    }

    @Test
    void lowerObjectiveRevisionCannotOverwriteNewerProjection() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);

        coordinator.publish(PLAYER_ID, state(LIFE_ID, 1, 2, "new-objectives"));
        coordinator.publish(PLAYER_ID, state(LIFE_ID, 1, 1, "old-objectives"));

        assertEquals(List.of("new-objectives"), rendered);
    }

    @Test
    void lifeChangeClearsOldProjectionBeforeTheNewRefreshCompletes() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = coordinator(gateway, sessions, rendered);
        UUID newLifeId = UUID.fromString("00000000-0000-0000-0000-000000000499");

        coordinator.publish(PLAYER_ID, state(LIFE_ID, 1, "old-life"));
        sessions.store(login(newLifeId));
        coordinator.refresh(PLAYER_ID);

        assertEquals(List.of("old-life", "none"), rendered);
        assertEquals(1, gateway.requests.size());
    }

    @Test
    void dispatcherFailureReleasesTheInFlightStateForRetry() {
        PlayerSessionCache sessions = sessions(LIFE_ID);
        RecordingGateway gateway = new RecordingGateway();
        List<String> rendered = new ArrayList<>();
        TrackedQuestRefreshCoordinator coordinator = new TrackedQuestRefreshCoordinator(
                gateway,
                sessions,
                action -> {
                    throw new IllegalStateException("dispatcher unavailable");
                },
                (playerId, tracked) -> rendered.add(tracked == null ? "none" : tracked.questId()),
                new NoOpLogger());

        coordinator.refresh(PLAYER_ID);
        gateway.requests.getFirst().complete(state(LIFE_ID, 1, "first"));
        coordinator.refresh(PLAYER_ID);

        assertEquals(2, gateway.requests.size());
        assertTrue(rendered.isEmpty());
    }

    private static TrackedQuestRefreshCoordinator coordinator(
            RecordingGateway gateway,
            PlayerSessionCache sessions,
            List<String> rendered) {
        return new TrackedQuestRefreshCoordinator(
                gateway,
                sessions,
                Runnable::run,
                (playerId, tracked) -> rendered.add(tracked == null ? "none" : tracked.questId()),
                new NoOpLogger());
    }

    private static PlayerSessionCache sessions(UUID lifeId) {
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(login(lifeId));
        return sessions;
    }

    private static PlayerLoginResult login(UUID lifeId) {
        return new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "QuestTester"),
                new LifeSnapshot(lifeId, ACCOUNT_ID, 1, "alive", null));
    }

    private static QuestInteractionState state(UUID lifeId, long revision, String questId) {
        return state(lifeId, revision, 0, questId);
    }

    private static QuestInteractionState state(
            UUID lifeId,
            long revision,
            long objectiveRevision,
            String questId) {
        return new QuestInteractionState(
                1,
                ACCOUNT_ID,
                lifeId,
                new QuestRevisionVector(1, revision, objectiveRevision, "definitions"),
                List.of(),
                new TrackedQuestSnapshot(questId, questId, "active", List.of(), "next"),
                2_000);
    }

    private static final class RecordingGateway implements TrackedQuestRefreshCoordinator.Gateway {
        private final List<CompletableFuture<QuestInteractionState>> requests = new ArrayList<>();

        @Override
        public CompletableFuture<QuestInteractionState> fetch(UUID accountId) {
            assertEquals(ACCOUNT_ID, accountId);
            CompletableFuture<QuestInteractionState> request = new CompletableFuture<>();
            requests.add(request);
            return request;
        }
    }

    private static final class NoOpLogger implements AdapterLogger {
        @Override
        public void debug(String message) {}

        @Override
        public void info(String message) {}

        @Override
        public void warn(String message) {}

        @Override
        public void warn(String message, Throwable error) {}

        @Override
        public void error(String message, Throwable error) {}
    }
}
