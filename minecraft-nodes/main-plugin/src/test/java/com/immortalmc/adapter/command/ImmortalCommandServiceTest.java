package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
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
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthRunner(),
                null,
                new SpiritRootDetectorAdminRunner(
                        new EntityInteractionRegistry(repository),
                        new SpiritRootDetectorAdminMessages(),
                        new RecordingAdapterLogger()),
                new HealthCommandMessages());
        EntityInteractionEntity detector = new EntityInteractionEntity(
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "VILLAGER");
        List<String> sentMessages = new ArrayList<>();

        service.execute(
                new String[] {"spirit-root-detector", "set"},
                ImmortalCommandSource.player(
                        UUID.fromString("00000000-0000-0000-0000-000000000010"), detector),
                sentMessages::add);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "spirit-root-detect-1", "spirit-root-detect", detector.binding(), "VILLAGER", true, false)),
                repository.load());
        assertEquals(
                List.of("Spirit-root detector spirit-root-detect-1 saved for entity "
                        + "30000000-0000-0000-0000-000000000001 in world. Total detectors: 1."),
                sentMessages);
    }

    @Test
    void detectorCreateListAndRemoveCommandsRunAdminActions() {
        InMemoryEntityInteractionRepository repository = new InMemoryEntityInteractionRepository();
        ImmortalCommandService service = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthRunner(),
                null,
                new SpiritRootDetectorAdminRunner(
                        new EntityInteractionRegistry(repository),
                        new SpiritRootDetectorAdminMessages(),
                        new RecordingAdapterLogger()),
                new HealthCommandMessages());
        EntityInteractionEntity spawned = new EntityInteractionEntity(
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000010")),
                "VILLAGER");
        UUID minecraftUuid = UUID.fromString("00000000-0000-0000-0000-000000000010");
        List<String> sentMessages = new ArrayList<>();
        List<EntityBinding> deletedEntities = new ArrayList<>();

        service.execute(
                new String[] {"spirit-root-detector", "create"},
                ImmortalCommandSource.playerWithSpawner(minecraftUuid, detectorId -> spawned),
                sentMessages::add);
        service.execute(
                new String[] {"spirit-root-detector", "list"},
                ImmortalCommandSource.player(minecraftUuid),
                sentMessages::add);
        service.execute(
                new String[] {"spirit-root-detector", "remove"},
                ImmortalCommandSource.player(minecraftUuid, spawned, binding -> {
                    deletedEntities.add(binding);
                    return true;
                }),
                sentMessages::add);

        assertEquals(List.of(), repository.load());
        assertEquals(List.of(spawned.binding()), deletedEntities);
        assertEquals(
                List.of(
                        "Spirit-root detector spirit-root-detect-1 created as VILLAGER in world. Total detectors: 1.",
                        "Spirit-root detectors: 1 configured.",
                        "- spirit-root-detect-1 VILLAGER world/30000000-0000-0000-0000-000000000010 protected=true",
                        "Spirit-root detector spirit-root-detect-1 removed and entity deleted. Total detectors: 0."),
                sentMessages);
    }

    private static HealthCommandRunner healthRunner() {
        return new HealthCommandRunner(
                () -> CompletableFuture.completedFuture(new HealthCheckResult("game-service", "ok", "0.1.0")),
                new HealthCommandMessages(),
                new RecordingAdapterLogger(),
                Runnable::run);
    }

    private static final class InMemoryEntityInteractionRepository implements EntityInteractionRepository {
        private List<EntityInteractionDefinition> interactions = new ArrayList<>();

        @Override
        public List<EntityInteractionDefinition> load() {
            return List.copyOf(interactions);
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {
            this.interactions = new ArrayList<>(interactions);
        }
    }
}
