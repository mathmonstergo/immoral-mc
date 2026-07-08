package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.client.SpiritRootSnapshot;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class SpiritRootCommandRunnerTest {
    @Test
    void consoleSenderCannotDetectSpiritRoot() {
        SpiritRootCommandRunner runner = new SpiritRootCommandRunner(
                accountId -> CompletableFuture.completedFuture(detectionResult(false)),
                new PlayerSessionCache(),
                new SpiritRootCommandMessages(),
                Runnable::run);
        List<String> messages = new ArrayList<>();

        runner.run(ImmortalCommandSource.console(), messages::add);

        assertEquals(List.of("Only players can detect spirit roots."), messages);
    }

    @Test
    void missingLoginCacheFailsClosed() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        SpiritRootCommandRunner runner = new SpiritRootCommandRunner(
                accountId -> CompletableFuture.completedFuture(detectionResult(false)),
                new PlayerSessionCache(),
                new SpiritRootCommandMessages(),
                Runnable::run);
        List<String> messages = new ArrayList<>();

        runner.run(ImmortalCommandSource.player(minecraftUuid), messages::add);

        assertEquals(List.of("ImmortalMC profile is not loaded yet. Rejoin or wait for login sync."), messages);
    }

    @Test
    void successfulDetectionUsesCachedAccountAndDispatchesResult() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        UUID accountId = UUID.fromString("10000000-0000-0000-0000-000000000001");
        CompletableFuture<SpiritRootDetectionResult> detectionFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        sessionCache.store(loginResult(minecraftUuid, accountId));
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        List<UUID> requestedAccountIds = new ArrayList<>();
        SpiritRootCommandRunner runner = new SpiritRootCommandRunner(
                requestedAccountId -> {
                    requestedAccountIds.add(requestedAccountId);
                    return detectionFuture;
                },
                sessionCache,
                new SpiritRootCommandMessages(),
                dispatcher::dispatch);
        List<String> messages = new ArrayList<>();

        runner.run(ImmortalCommandSource.player(minecraftUuid), messages::add);
        detectionFuture.complete(detectionResult(false));

        assertEquals(List.of(accountId), requestedAccountIds);
        assertEquals(List.of("Detecting spirit root..."), messages);
        dispatcher.runAll();

        assertEquals(
                List.of("Detecting spirit root...", "Spirit root: Dual Root (dual), elements=fire, water"),
                messages);
    }

    @Test
    void failedDetectionReportsFailure() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        UUID accountId = UUID.fromString("10000000-0000-0000-0000-000000000001");
        CompletableFuture<SpiritRootDetectionResult> detectionFuture = new CompletableFuture<>();
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        sessionCache.store(loginResult(minecraftUuid, accountId));
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        SpiritRootCommandRunner runner = new SpiritRootCommandRunner(
                requestedAccountId -> detectionFuture,
                sessionCache,
                new SpiritRootCommandMessages(),
                dispatcher::dispatch);
        List<String> messages = new ArrayList<>();

        runner.run(ImmortalCommandSource.player(minecraftUuid), messages::add);
        detectionFuture.completeExceptionally(
                new GameServiceException("Game Service spirit-root detection failed with HTTP 503"));
        dispatcher.runAll();

        assertEquals(
                List.of(
                        "Detecting spirit root...",
                        "Spirit root unavailable: Game Service spirit-root detection failed with HTTP 503"),
                messages);
    }

    private static PlayerLoginResult loginResult(UUID minecraftUuid, UUID accountId) {
        return new PlayerLoginResult(
                new AccountSnapshot(accountId, minecraftUuid, "Sensen"),
                new LifeSnapshot(
                        UUID.fromString("20000000-0000-0000-0000-000000000001"),
                        accountId,
                        1,
                        "alive",
                        null));
    }

    private static SpiritRootDetectionResult detectionResult(boolean alreadyDetected) {
        return new SpiritRootDetectionResult(
                UUID.fromString("20000000-0000-0000-0000-000000000001"),
                new SpiritRootSnapshot("dual", "Dual Root", List.of("fire", "water"), null, null),
                alreadyDetected);
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
