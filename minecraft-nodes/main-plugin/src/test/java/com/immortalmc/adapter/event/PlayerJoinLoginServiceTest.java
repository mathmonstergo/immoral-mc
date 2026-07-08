package com.immortalmc.adapter.event;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class PlayerJoinLoginServiceTest {
    @Test
    void successfulJoinLoginCachesSnapshotOnMainThread() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        CompletableFuture<PlayerLoginResult> loginFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        List<String> messages = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> loginFuture,
                sessionCache,
                new PlayerJoinMessages(),
                dispatcher::dispatch);

        service.loginOnJoin(minecraftUuid, "Sensen", messages::add);
        loginFuture.complete(loginResult(minecraftUuid, "Sensen"));

        assertEquals(List.of("Loading ImmortalMC profile..."), messages);
        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isEmpty());

        dispatcher.runAll();

        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isPresent());
        assertEquals(
                List.of("Loading ImmortalMC profile...", "ImmortalMC profile loaded."),
                messages);
    }

    @Test
    void failedJoinLoginReportsFailureAndDoesNotCacheFallbackState() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000011");
        CompletableFuture<PlayerLoginResult> loginFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        List<String> messages = new ArrayList<>();
        PlayerJoinLoginService service = new PlayerJoinLoginService(
                (uuid, name) -> loginFuture,
                sessionCache,
                new PlayerJoinMessages(),
                dispatcher::dispatch);

        service.loginOnJoin(minecraftUuid, "Downstream", messages::add);
        loginFuture.completeExceptionally(new GameServiceException("Game Service login failed with HTTP 503"));
        dispatcher.runAll();

        assertTrue(sessionCache.findByMinecraftUuid(minecraftUuid).isEmpty());
        assertEquals(
                List.of(
                        "Loading ImmortalMC profile...",
                        "ImmortalMC profile unavailable: Game Service login failed with HTTP 503"),
                messages);
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
