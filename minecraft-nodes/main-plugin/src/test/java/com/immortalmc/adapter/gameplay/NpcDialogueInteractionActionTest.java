package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.dialogue.NpcDialogueAudience;
import com.immortalmc.adapter.dialogue.NpcDialogueDefinition;
import com.immortalmc.adapter.dialogue.NpcDialoguePresenter;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.dialogue.NpcDialogueRepository;
import com.immortalmc.adapter.dialogue.NpcDialogueScheduler;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

class NpcDialogueInteractionActionTest {
    private static final UUID MINECRAFT_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");

    @Test
    void startsConfiguredDialogueAndLogsEvent() {
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        RecordingAudience audience = new RecordingAudience();
        NpcDialogueRegistry registry = new NpcDialogueRegistry(new InMemoryNpcDialogueRepository(Map.of(
                "old-man", dialogue("old-man"))));
        registry.reload();
        NpcDialogueInteractionAction action = new NpcDialogueInteractionAction(
                registry,
                new NpcDialoguePresenter(NpcDialogueScheduler.immediate()),
                logger,
                player -> audience);

        action.handle(
                interaction(Map.of("dialogue-id", "old-man")),
                new BukkitEntityInteractionContext(player(), entity()));

        assertEquals(
                List.of("npc_dialogue_started minecraft_uuid="
                        + MINECRAFT_UUID
                        + " interaction_id=npc-dialogue-1 dialogue_id=old-man"),
                logger.messagesAt("info"));
        assertEquals(List.of("§6老村民§7: §f年轻人，你身上有一股未定的气。"), audience.npcLines());
        assertEquals(List.of("entity.villager.ambient"), audience.sounds());
    }

    @Test
    void missingDialogueIdMetadataWarnsWithoutFallbackDialogue() {
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        RecordingAudience audience = new RecordingAudience();
        NpcDialogueRegistry registry = new NpcDialogueRegistry(new InMemoryNpcDialogueRepository(Map.of()));
        registry.reload();
        NpcDialogueInteractionAction action = new NpcDialogueInteractionAction(
                registry,
                new NpcDialoguePresenter(NpcDialogueScheduler.immediate()),
                logger,
                player -> audience);

        action.handle(interaction(Map.of()), new BukkitEntityInteractionContext(player(), entity()));

        assertEquals(List.of(), audience.messages());
        assertEquals(
                List.of("npc_dialogue_rejected minecraft_uuid="
                        + MINECRAFT_UUID
                        + " interaction_id=npc-dialogue-1 reason=dialogue_id_missing"),
                logger.messagesAt("warn"));
    }

    @Test
    void missingDialogueContentWarnsWithoutFallbackDialogue() {
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        RecordingAudience audience = new RecordingAudience();
        NpcDialogueRegistry registry = new NpcDialogueRegistry(new InMemoryNpcDialogueRepository(Map.of()));
        registry.reload();
        NpcDialogueInteractionAction action = new NpcDialogueInteractionAction(
                registry,
                new NpcDialoguePresenter(NpcDialogueScheduler.immediate()),
                logger,
                player -> audience);

        action.handle(
                interaction(Map.of("dialogue-id", "missing")),
                new BukkitEntityInteractionContext(player(), entity()));

        assertEquals(List.of(), audience.messages());
        assertEquals(
                List.of("npc_dialogue_rejected minecraft_uuid="
                        + MINECRAFT_UUID
                        + " interaction_id=npc-dialogue-1 dialogue_id=missing reason=dialogue_missing"),
                logger.messagesAt("warn"));
    }

    private static EntityInteractionDefinition interaction(Map<String, String> metadata) {
        return new EntityInteractionDefinition(
                "npc-dialogue-1",
                NpcDialogueInteractionAction.ACTION,
                new EntityBinding("world", UUID.fromString("30000000-0000-0000-0000-000000000001")),
                "VILLAGER",
                true,
                false,
                metadata);
    }

    private static NpcDialogueDefinition dialogue(String id) {
        return new NpcDialogueDefinition(
                id,
                "初入凡尘",
                "老村民",
                List.of("§6§l任务开始"),
                List.of("年轻人，你身上有一股未定的气。"),
                30,
                "entity.villager.ambient",
                1.0f);
    }

    private static Player player() {
        return proxy(Player.class, Map.of(
                "getUniqueId", MINECRAFT_UUID,
                "getLocation", new Location(null, 0.0, 0.0, 0.0)));
    }

    private static Entity entity() {
        return proxy(Entity.class, Map.of());
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
        if (type == void.class) {
            return null;
        }
        return 0;
    }

    private static final class RecordingAudience implements NpcDialogueAudience {
        private final List<String> messages = new ArrayList<>();
        private final List<String> sounds = new ArrayList<>();

        @Override
        public void sendMessage(String message) {
            messages.add(message);
        }

        @Override
        public void playSound(String sound, float volume, float pitch) {
            sounds.add(sound);
        }

        List<String> messages() {
            return List.copyOf(messages);
        }

        List<String> npcLines() {
            return messages.stream()
                    .filter(message -> message.startsWith("§6老村民"))
                    .toList();
        }

        List<String> sounds() {
            return List.copyOf(sounds);
        }
    }

    private record InMemoryNpcDialogueRepository(Map<String, NpcDialogueDefinition> dialogues)
            implements NpcDialogueRepository {
        @Override
        public Map<String, NpcDialogueDefinition> loadAll() {
            return dialogues;
        }
    }
}
