package com.immortalmc.adapter.event;

import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.command.NpcDialogueAdminRunner;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.bukkit.entity.Entity;
import org.junit.jupiter.api.Test;

class EntityInteractionProtectionListenerTest {
    @Test
    void protectsCitizensNpcByPersistentUuidAfterEntityRespawn() {
        UUID citizensUuid = UUID.fromString("40000000-0000-0000-0000-000000000001");
        EntityInteractionDefinition definition = new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                new EntityBinding("old-world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "PLAYER",
                true,
                false,
                Map.of(
                        NpcDialogueAdminRunner.TARGET_PROVIDER_KEY, NpcDialogueAdminRunner.CITIZENS_PROVIDER,
                        NpcDialogueAdminRunner.CITIZENS_NPC_UUID_KEY, citizensUuid.toString()));
        EntityInteractionRegistry registry = new EntityInteractionRegistry(new FixedRepository(definition));
        registry.reload();
        EntityInteractionProtectionListener listener = new EntityInteractionProtectionListener(
                registry,
                entity -> Optional.of(citizensUuid));

        assertTrue(listener.isProtected(proxy(Entity.class)));
    }

    private static <T> T proxy(Class<T> type) {
        return type.cast(Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> null));
    }

    private record FixedRepository(EntityInteractionDefinition definition) implements EntityInteractionRepository {
        @Override
        public List<EntityInteractionDefinition> load() {
            return List.of(definition);
        }

        @Override
        public void save(List<EntityInteractionDefinition> interactions) {}
    }
}
