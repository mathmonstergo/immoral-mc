package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class HealthCommandRunnerTest {
    @Test
    void dispatchesSuccessfulHealthResultBackToMainThread() {
        CompletableFuture<HealthCheckResult> healthCheck = new CompletableFuture<>();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<String> sentMessages = new ArrayList<>();
        HealthCommandRunner runner = new HealthCommandRunner(
                () -> healthCheck, new HealthCommandMessages(), logger, dispatcher::dispatch);

        runner.run(sentMessages::add);
        healthCheck.complete(new HealthCheckResult("game-service", "ok", "0.1.0"));

        assertEquals(List.of("Checking Game Service health..."), sentMessages);

        dispatcher.runAll();

        assertEquals(
                List.of("Checking Game Service health...", "Game Service: game-service ok (0.1.0)"),
                sentMessages);
        assertEquals(
                List.of("health_check_success service=game-service status=ok version=0.1.0"),
                logger.messagesAt("info"));
    }

    @Test
    void dispatchesFailedHealthResultBackToMainThread() {
        CompletableFuture<HealthCheckResult> healthCheck = new CompletableFuture<>();
        RecordingDispatcher dispatcher = new RecordingDispatcher();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        List<String> sentMessages = new ArrayList<>();
        HealthCommandRunner runner = new HealthCommandRunner(
                () -> healthCheck, new HealthCommandMessages(), logger, dispatcher::dispatch);

        runner.run(sentMessages::add);
        healthCheck.completeExceptionally(new GameServiceException("Game Service health check failed with HTTP 503"));
        dispatcher.runAll();

        assertEquals(
                List.of(
                        "Checking Game Service health...",
                        "Game Service unavailable: Game Service health check failed with HTTP 503"),
                sentMessages);
        assertEquals(
                List.of("health_check_failure reason=Game Service health check failed with HTTP 503"),
                logger.messagesAt("warn"));
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
