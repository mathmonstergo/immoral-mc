package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.client.SpiritRootSnapshot;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class SpiritRootDetectionUseCaseTest {
    @Test
    void successDispatchesResultFeedbackAndSuccessCallbackOnMainThread() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        UUID accountId = UUID.fromString("10000000-0000-0000-0000-000000000001");
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        sessionCache.store(loginResult(minecraftUuid, accountId));
        CompletableFuture<SpiritRootDetectionResult> detectionFuture = new CompletableFuture<>();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<SpiritRootDetectionResult> successfulResults = new ArrayList<>();
        SpiritRootDetectionUseCase useCase = new SpiritRootDetectionUseCase(
                requestedAccountId -> detectionFuture,
                sessionCache,
                new SpiritRootCommandMessages(),
                logger,
                dispatcher::dispatch);
        List<String> messages = new ArrayList<>();

        useCase.detectForPlayer(minecraftUuid, "spirit_root_detector", messages::add, successfulResults::add);
        detectionFuture.complete(detectionResult(false));

        assertEquals(List.of("Detecting spirit root..."), messages);
        assertEquals(List.of(), successfulResults);
        dispatcher.runAll();

        assertEquals(
                List.of("Detecting spirit root...", "Spirit root: Dual Root (dual), elements=fire, water"),
                messages);
        assertEquals(List.of(detectionResult(false)), successfulResults);
        assertEquals(
                List.of(
                        "spirit_root_detector_success minecraft_uuid=00000000-0000-0000-0000-000000000010 account_id=10000000-0000-0000-0000-000000000001 life_id=20000000-0000-0000-0000-000000000001 quality=dual elements=fire,water already_detected=false"),
                logger.messagesAt("info"));
    }

    @Test
    void failureDoesNotRunSuccessCallback() {
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        UUID accountId = UUID.fromString("10000000-0000-0000-0000-000000000001");
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        sessionCache.store(loginResult(minecraftUuid, accountId));
        CompletableFuture<SpiritRootDetectionResult> detectionFuture = new CompletableFuture<>();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        SpiritRootDetectionUseCase useCase = new SpiritRootDetectionUseCase(
                requestedAccountId -> detectionFuture,
                sessionCache,
                new SpiritRootCommandMessages(),
                new RecordingAdapterLogger(),
                dispatcher::dispatch);
        List<SpiritRootDetectionResult> successfulResults = new ArrayList<>();
        List<String> messages = new ArrayList<>();

        useCase.detectForPlayer(minecraftUuid, "spirit_root_detector", messages::add, successfulResults::add);
        detectionFuture.completeExceptionally(
                new GameServiceException("Game Service spirit-root detection failed with HTTP 503"));
        dispatcher.runAll();

        assertEquals(List.of(), successfulResults);
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
