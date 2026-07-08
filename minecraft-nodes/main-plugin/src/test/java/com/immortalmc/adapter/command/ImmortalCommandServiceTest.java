package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.SpiritRootDetectorRegistry;
import com.immortalmc.adapter.content.SpiritRootDetectorRepository;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
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
                        new RecordingAdapterLogger(),
                        Runnable::run),
                new HealthCommandMessages());
        List<String> sentMessages = new ArrayList<>();

        service.execute(new String[] {}, sentMessages::add);

        assertEquals(List.of("Usage: /immortal <health|spirit-root|spirit-root-detector>"), sentMessages);
    }

    @Test
    void healthCommandRunsHealthCheck() {
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                new HealthCommandRunner(
                        () -> CompletableFuture.completedFuture(
                                new HealthCheckResult("game-service", "ok", "0.1.0")),
                        new HealthCommandMessages(),
                        new RecordingAdapterLogger(),
                        Runnable::run),
                new HealthCommandMessages());
        List<String> sentMessages = new ArrayList<>();

        service.execute(new String[] {"health"}, sentMessages::add);

        assertEquals(
                List.of("Checking Game Service health...", "Game Service: game-service ok (0.1.0)"),
                sentMessages);
    }

    @Test
    void detectorSetCommandRunsAdminSetter() {
        InMemorySpiritRootDetectorRepository repository = new InMemorySpiritRootDetectorRepository();
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthRunner(),
                null,
                new SpiritRootDetectorAdminRunner(
                        new SpiritRootDetectorRegistry(repository),
                        new SpiritRootDetectorAdminMessages(),
                        new RecordingAdapterLogger()),
                new HealthCommandMessages());
        EntityBinding detector = new EntityBinding(
                "world", UUID.fromString("30000000-0000-0000-0000-000000000001"));
        List<String> sentMessages = new ArrayList<>();

        service.execute(
                new String[] {"spirit-root-detector", "set"},
                ImmortalCommandSource.player(
                        UUID.fromString("00000000-0000-0000-0000-000000000010"), detector),
                sentMessages::add);

        assertEquals(List.of(detector), repository.load());
        assertEquals(
                List.of("Spirit-root detector saved for entity 30000000-0000-0000-0000-000000000001 in world. Total detectors: 1."),
                sentMessages);
    }

    private static HealthCommandRunner healthRunner() {
        return new HealthCommandRunner(
                () -> CompletableFuture.completedFuture(new HealthCheckResult("game-service", "ok", "0.1.0")),
                new HealthCommandMessages(),
                new RecordingAdapterLogger(),
                Runnable::run);
    }

    private static final class InMemorySpiritRootDetectorRepository implements SpiritRootDetectorRepository {
        private List<EntityBinding> bindings = new ArrayList<>();

        @Override
        public List<EntityBinding> load() {
            return List.copyOf(bindings);
        }

        @Override
        public void save(List<EntityBinding> bindings) {
            this.bindings = new ArrayList<>(bindings);
        }
    }
}
