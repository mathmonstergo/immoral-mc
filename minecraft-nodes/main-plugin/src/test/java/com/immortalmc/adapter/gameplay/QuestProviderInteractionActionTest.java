package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

class QuestProviderInteractionActionTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ENTITY_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void validBindingOpensQuestGuiOnceWithStableIdentity() {
        AtomicInteger opens = new AtomicInteger();
        AtomicReference<UUID> openedNpc = new AtomicReference<>();
        QuestProviderInteractionAction action = new QuestProviderInteractionAction(
                (player, interactionId, npcId, providerId) -> {
                    opens.incrementAndGet();
                    assertEquals("old-man-quests", interactionId);
                    assertEquals("old-man", providerId);
                    openedNpc.set(npcId);
                },
                new RecordingAdapterLogger());

        action.handle(definition(Map.of(
                        QuestProviderInteractionAction.PROVIDER_ID_KEY, "old-man",
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, NPC_ID.toString())),
                context());

        assertEquals(1, opens.get());
        assertEquals(NPC_ID, openedNpc.get());
    }

    @Test
    void missingProviderIdDoesNotOpenGui() {
        AtomicInteger opens = new AtomicInteger();
        QuestProviderInteractionAction action = new QuestProviderInteractionAction(
                (player, interactionId, npcId, providerId) -> opens.incrementAndGet(),
                new RecordingAdapterLogger());

        action.handle(definition(Map.of()), context());

        assertEquals(0, opens.get());
    }

    @Test
    void invalidCitizensUuidDoesNotOpenGui() {
        AtomicInteger opens = new AtomicInteger();
        QuestProviderInteractionAction action = new QuestProviderInteractionAction(
                (player, interactionId, npcId, providerId) -> opens.incrementAndGet(),
                new RecordingAdapterLogger());

        action.handle(definition(Map.of(
                        QuestProviderInteractionAction.PROVIDER_ID_KEY, "old-man",
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, "not-a-uuid")),
                context());

        assertEquals(0, opens.get());
    }

    private static EntityInteractionDefinition definition(Map<String, String> metadata) {
        return new EntityInteractionDefinition(
                "old-man-quests",
                QuestProviderInteractionAction.ACTION,
                new EntityBinding("world", ENTITY_ID),
                "PLAYER",
                true,
                false,
                metadata);
    }

    private static BukkitEntityInteractionContext context() {
        return new BukkitEntityInteractionContext(
                proxy(Player.class, Map.of("getUniqueId", PLAYER_ID)),
                proxy(Entity.class, Map.of("getUniqueId", ENTITY_ID)));
    }

    @SuppressWarnings("unchecked")
    private static <T> T proxy(Class<T> type, Map<String, Object> returns) {
        return (T) Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> returns.containsKey(method.getName())
                        ? returns.get(method.getName())
                        : defaultValue(method.getReturnType()));
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
}
