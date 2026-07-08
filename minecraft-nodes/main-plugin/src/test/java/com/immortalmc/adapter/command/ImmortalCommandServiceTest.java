package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.HealthCheckResult;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class ImmortalCommandServiceTest {
    @Test
    void emptyCommandShowsUsage() {
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                new HealthCommandRunner(
                        () -> CompletableFuture.completedFuture(
                                new HealthCheckResult("game-service", "ok", "0.1.0")),
                        new HealthCommandMessages(),
                        Runnable::run),
                new HealthCommandMessages());
        List<String> sentMessages = new ArrayList<>();

        service.execute(new String[] {}, sentMessages::add);

        assertEquals(List.of("Usage: /immortal health"), sentMessages);
    }

    @Test
    void healthCommandRunsHealthCheck() {
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                new HealthCommandRunner(
                        () -> CompletableFuture.completedFuture(
                                new HealthCheckResult("game-service", "ok", "0.1.0")),
                        new HealthCommandMessages(),
                        Runnable::run),
                new HealthCommandMessages());
        List<String> sentMessages = new ArrayList<>();

        service.execute(new String[] {"health"}, sentMessages::add);

        assertEquals(
                List.of("Checking Game Service health...", "Game Service: game-service ok (0.1.0)"),
                sentMessages);
    }
}
