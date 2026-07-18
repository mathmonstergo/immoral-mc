package com.immortalmc.adapter.event;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;

class PlayerJoinLoginServiceTest {
    @Test
    void successfulJoinLoginCachesSnapshotOnMainThread() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        CompletableFuture<PlayerLoginResult> loginFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<String> messages = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> loginFuture,
                sessionCache,
                logger,
                dispatcher::dispatch);

        service.loginOnJoin(minecraftUuid, "Sensen", messages::add);
        loginFuture.complete(loginResult(minecraftUuid, "Sensen"));

        assertEquals(List.of(), messages);
        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isEmpty());

        dispatcher.runAll();

        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isPresent());
        assertEquals(List.of(), messages);
        assertEquals(
                List.of(
                        "player_login_success player_name=Sensen minecraft_uuid=00000000-0000-0000-0000-000000000010 account_id=10000000-0000-0000-0000-000000000001 life_id=20000000-0000-0000-0000-000000000001"),
                logger.messagesAt("info"));
    }

    @Test
    void failedJoinLoginReportsFailureAndDoesNotCacheFallbackState() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000011");
        CompletableFuture<PlayerLoginResult> loginFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<String> messages = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> loginFuture,
                sessionCache,
                logger,
                dispatcher::dispatch);

        service.loginOnJoin(minecraftUuid, "Downstream", messages::add);
        loginFuture.completeExceptionally(new GameServiceException("Game Service login failed with HTTP 503"));
        dispatcher.runAll();

        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isEmpty());
        assertEquals(
                List.of(
                        "player_login_failure player_name=Downstream minecraft_uuid=00000000-0000-0000-0000-000000000011 reason=Game Service login failed with HTTP 503"),
                logger.messagesAt("warn"));
        assertEquals(List.of(), messages);
    }

    @Test
    void invalidatedAttemptCannotPublishAfterTheSamePlayerRejoins() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000012");
        CompletableFuture<PlayerLoginResult> oldLogin = new CompletableFuture<>();
        CompletableFuture<PlayerLoginResult> newLogin = new CompletableFuture<>();
        AtomicInteger calls = new AtomicInteger();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        List<String> successes = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> calls.getAndIncrement() == 0 ? oldLogin : newLogin,
                sessionCache,
                new RecordingAdapterLogger(),
                dispatcher::dispatch,
                result -> successes.add(result.account().playerName()),
                ignored -> true);

        service.loginOnJoin(minecraftUuid, "OldJoin", ignored -> {});
        service.invalidate(minecraftUuid);
        service.loginOnJoin(minecraftUuid, "NewJoin", ignored -> {});
        newLogin.complete(loginResult(minecraftUuid, "NewJoin"));
        dispatcher.runAll();
        oldLogin.complete(loginResult(minecraftUuid, "OldJoin"));
        dispatcher.runAll();

        assertEquals("NewJoin", sessionCache.findByMinecraftUuid(minecraftUuid)
                .orElseThrow()
                .account()
                .playerName());
        assertEquals(List.of("NewJoin"), successes);
    }

    @Test
    void successfulResponseForOfflinePlayerIsDiscardedBeforeCachingOrCallbacks() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000013");
        CompletableFuture<PlayerLoginResult> loginFuture = new CompletableFuture<>();
        AtomicBoolean online = new AtomicBoolean(true);
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        List<PlayerLoginResult> successes = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> loginFuture,
                sessionCache,
                new RecordingAdapterLogger(),
                dispatcher::dispatch,
                successes::add,
                ignored -> online.get());

        service.loginOnJoin(minecraftUuid, "Disconnected", ignored -> {});
        online.set(false);
        loginFuture.complete(loginResult(minecraftUuid, "Disconnected"));
        dispatcher.runAll();

        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isEmpty());
        assertTrue(successes.isEmpty());
    }

    private static PlayerLoginResult loginResult(UUID minecraftUuid, String playerName) {
        return new PlayerLoginResult(
                new AccountSnapshot(
                        UUID.fromString("10000000-0000-0000-0000-000000000001"), minecraftUuid, playerName),
                new LifeSnapshot(
                        UUID.fromString("20000000-0000-0000-0000-000000000001"),
                        UUID.fromString("10000000-0000-0000-0000-000000000001"),
                        1,
                        "alive",
                        null));
    }

    private static final class RecordingDispatcher {
        private final List<Runnable> tasks = new ArrayList<>();

        void dispatch(Runnable task) {
            tasks.add(task);
        }

        void runAll() {
            for (Runnable task : List.copyOf(tasks)) {
                task.run();
            }
            tasks.clear();
        }
    }
}
