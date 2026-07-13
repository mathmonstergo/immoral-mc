package com.immortalmc.adapter.citizens;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.command.NpcDialogueAdminRunner;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.interaction.InteractionDebouncer;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.World;
import org.junit.jupiter.api.Test;

class CitizensNpcInteractionHandlerTest {
    private static final UUID PLAYER_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID CITIZENS_UUID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void routesPersistentCitizensBindingWhenBukkitEntityChanged() {
        AtomicInteger routed = new AtomicInteger();
        CitizensNpcInteractionHandler handler = handlerWith(
                List.of(citizensDialogue("30000000-0000-0000-0000-000000000001")),
                new EntityInteractionActionRouter<>(Map.of("npc-dialogue", (definition, context) -> routed.incrementAndGet())),
                new InteractionDebouncer(Duration.ofMillis(500), () -> 0L));

        boolean handled = handler.handle(CITIZENS_UUID, player(), entity());

        assertTrue(handled);
        assertTrue(routed.get() == 1);
    }

    @Test
    void unknownCitizensNpcIsNotHandled() {
        CitizensNpcInteractionHandler handler = handlerWith(
                List.of(),
                new EntityInteractionActionRouter<>(Map.of()),
                new InteractionDebouncer(Duration.ofMillis(500), () -> 0L));

        assertFalse(handler.handle(
                CITIZENS_UUID,
                player(),
                entity("world", UUID.fromString("30000000-0000-0000-0000-000000000008"))));
    }

    @Test
    void rapidDuplicateClickIsHandledButRoutesOnlyOnce() {
        AtomicInteger routed = new AtomicInteger();
        CitizensNpcInteractionHandler handler = handlerWith(
                List.of(citizensDialogue("30000000-0000-0000-0000-000000000001")),
                new EntityInteractionActionRouter<>(Map.of("npc-dialogue", (definition, context) -> routed.incrementAndGet())),
                new InteractionDebouncer(Duration.ofMillis(500), () -> 0L));

        assertTrue(handler.handle(CITIZENS_UUID, player(), entity()));
        assertTrue(handler.handle(CITIZENS_UUID, player(), entity()));
        assertTrue(routed.get() == 1);
    }

    @Test
    void routesLegacyEntityBindingForCitizensNpcDuringMigration() {
        UUID currentEntityUuid = UUID.fromString("30000000-0000-0000-0000-000000000007");
        AtomicInteger routed = new AtomicInteger();
        EntityInteractionDefinition legacy = new EntityInteractionDefinition(
                "npc-dialogue-legacy",
                "npc-dialogue",
                new EntityBinding("world", currentEntityUuid),
                "PLAYER",
                true,
                false,
                Map.of("dialogue-id", "old-man"));
        CitizensNpcInteractionHandler handler = handlerWith(
                List.of(legacy),
                new EntityInteractionActionRouter<>(Map.of("npc-dialogue", (definition, context) -> routed.incrementAndGet())),
                new InteractionDebouncer(Duration.ofMillis(500), () -> 0L));

        assertTrue(handler.handle(CITIZENS_UUID, player(), entity("world", currentEntityUuid)));
        assertTrue(routed.get() == 1);
    }

    private static CitizensNpcInteractionHandler handlerWith(
            List<EntityInteractionDefinition> definitions,
            EntityInteractionActionRouter<BukkitEntityInteractionContext> router,
            InteractionDebouncer debouncer) {
        InMemoryRepository repository = new InMemoryRepository(definitions);
        EntityInteractionRegistry registry = new EntityInteractionRegistry(repository);
        registry.reload();
        return new CitizensNpcInteractionHandler(registry, router, new RecordingAdapterLogger(), debouncer);
    }

    private static EntityInteractionDefinition citizensDialogue(String entityUuid) {
        return new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                new EntityBinding("old-world", UUID.fromString(entityUuid)),
                "PLAYER",
                true,
                false,
                Map.of(
                        NpcDialogueAdminRunner.TARGET_PROVIDER_KEY, NpcDialogueAdminRunner.CITIZENS_PROVIDER,
                        NpcDialogueAdminRunner.CITIZENS_NPC_UUID_KEY, CITIZENS_UUID.toString(),
                        "dialogue-id", "old-man"));
    }

    private static Player player() {
        return proxy(Player.class, Map.of("getUniqueId", PLAYER_UUID));
    }

    private static Entity entity() {
        return proxy(Entity.class, Map.of());
    }

    private static Entity entity(String worldName, UUID entityUuid) {
        World world = proxy(World.class, Map.of("getName", worldName));
        return proxy(Entity.class, Map.of("getWorld", world, "getUniqueId", entityUuid));
    }

    private static <T> T proxy(Class<T> type, Map<String, Object> returns) {
        return type.cast(Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> returns.getOrDefault(method.getName(), defaultValue(method.getReturnType()))));
    }

    private static Object defaultValue(Class<?> type) {
        if (!type.isPrimitive()) {
            return null;
        }
        if (type == boolean.class) {
            return false;
        }
        return 0;
    }

    private static final class InMemoryRepository implements EntityInteractionRepository {
        private List<EntityInteractionDefinition> definitions;

        private InMemoryRepository(List<EntityInteractionDefinition> definitions) {
            this.definitions = new ArrayList<>(definitions);
        }

        @Override
        public List<EntityInteractionDefinition> load() {
            return List.copyOf(definitions);
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {
            definitions = new ArrayList<>(interactions);
        }
    }
}
