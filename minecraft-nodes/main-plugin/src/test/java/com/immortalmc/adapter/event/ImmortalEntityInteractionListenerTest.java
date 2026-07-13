package com.immortalmc.adapter.event;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.junit.jupiter.api.Test;

class ImmortalEntityInteractionListenerTest {
    @Test
    void skipsCitizensNpcBeforeGenericBindingLookup() {
        AtomicInteger routed = new AtomicInteger();
        EntityInteractionRegistry registry = new EntityInteractionRegistry(new EmptyRepository());
        registry.reload();
        EntityInteractionActionRouter<BukkitEntityInteractionContext> router =
                new EntityInteractionActionRouter<>(Map.of("npc-dialogue", (definition, context) -> routed.incrementAndGet()));
        CitizensNpcResolver resolver = entity -> Optional.of(
                UUID.fromString("40000000-0000-0000-0000-000000000001"));
        ImmortalEntityInteractionListener listener = new ImmortalEntityInteractionListener(
                registry,
                router,
                new RecordingAdapterLogger(),
                resolver);
        PlayerInteractEntityEvent event = new PlayerInteractEntityEvent(
                proxy(Player.class),
                proxy(Entity.class),
                EquipmentSlot.HAND);

        listener.onPlayerInteractEntity(event);

        assertEquals(0, routed.get());
        assertFalse(event.isCancelled());
    }

    private static <T> T proxy(Class<T> type) {
        return type.cast(Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> defaultValue(method.getReturnType())));
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

    private static final class EmptyRepository implements EntityInteractionRepository {
        @Override
        public List<EntityInteractionDefinition> load() {
            return List.of();
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {}
    }
}
