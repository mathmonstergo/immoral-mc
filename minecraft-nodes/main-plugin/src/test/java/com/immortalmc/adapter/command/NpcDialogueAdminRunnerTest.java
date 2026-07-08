package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.content.EntityInteractionRepository;
import com.immortalmc.adapter.dialogue.NpcDialogueDefinition;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.dialogue.NpcDialogueRepository;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class NpcDialogueAdminRunnerTest {
    private static final UUID MINECRAFT_UUID = UUID.fromString("00000000-0000-0000-0000-000000000010");

    @Test
    void setBindsLookedAtEntityToDialogueWithoutManagingEntity() {
        InMemoryEntityInteractionRepository interactionRepository = new InMemoryEntityInteractionRepository();
        NpcDialogueAdminRunner runner = runnerWith(interactionRepository, dialogueRepository());
        EntityInteractionEntity target = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        List<String> messages = new ArrayList<>();

        runner.reload(ignored -> {});
        runner.setLookedAtEntityAsDialogue(
                ImmortalCommandSource.player(MINECRAFT_UUID, target),
                "old-man",
                messages::add);

        assertEquals(
                List.of(new EntityInteractionDefinition(
                        "npc-dialogue-1",
                        "npc-dialogue",
                        target.binding(),
                        "VILLAGER",
                        true,
                        false,
                        Map.of("dialogue-id", "old-man"))),
                interactionRepository.load());
        assertEquals(
                List.of("NPC dialogue npc-dialogue-1 bound to old-man for entity "
                        + "30000000-0000-0000-0000-000000000001 in world. Total NPC dialogues: 1."),
                messages);
    }

    @Test
    void setRejectsMissingDialogueContent() {
        InMemoryEntityInteractionRepository interactionRepository = new InMemoryEntityInteractionRepository();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        NpcDialogueAdminRunner runner = runnerWith(interactionRepository, dialogueRepository(Map.of()), logger);
        EntityInteractionEntity target = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        List<String> messages = new ArrayList<>();

        runner.reload(ignored -> {});
        runner.setLookedAtEntityAsDialogue(
                ImmortalCommandSource.player(MINECRAFT_UUID, target),
                "missing",
                messages::add);

        assertEquals(List.of(), interactionRepository.load());
        assertEquals(List.of("NPC dialogue missing is not loaded. Create dialogues/missing.yml and reload."), messages);
        assertEquals(
                List.of("npc_dialogue_admin_rejected minecraft_uuid="
                        + MINECRAFT_UUID
                        + " dialogue_id=missing reason=dialogue_missing"),
                logger.messagesAt("warn"));
    }

    @Test
    void listAndRemoveOnlyAffectNpcDialogueBindings() {
        InMemoryEntityInteractionRepository interactionRepository = new InMemoryEntityInteractionRepository();
        EntityInteractionEntity dialogueEntity = interactionEntity(
                "world", "30000000-0000-0000-0000-000000000001", "VILLAGER");
        EntityInteractionDefinition dialogue = new EntityInteractionDefinition(
                "npc-dialogue-1",
                "npc-dialogue",
                dialogueEntity.binding(),
                "VILLAGER",
                true,
                false,
                Map.of("dialogue-id", "old-man"));
        EntityInteractionDefinition detector = new EntityInteractionDefinition(
                "spirit-root-detect-1",
                "spirit-root-detect",
                binding("world", "30000000-0000-0000-0000-000000000002"),
                "VILLAGER",
                true);
        interactionRepository.replaceWith(List.of(dialogue, detector));
        NpcDialogueAdminRunner runner = runnerWith(interactionRepository, dialogueRepository());
        List<String> messages = new ArrayList<>();

        runner.reload(ignored -> {});
        runner.listDialogues(messages::add);
        runner.removeLookedAtDialogue(ImmortalCommandSource.player(MINECRAFT_UUID, dialogueEntity), messages::add);

        assertEquals(List.of(detector), interactionRepository.load());
        assertEquals(
                List.of(
                        "NPC dialogues: 1 configured.",
                        "- npc-dialogue-1 old-man VILLAGER world/30000000-0000-0000-0000-000000000001 protected=true",
                        "NPC dialogue npc-dialogue-1 removed. Total NPC dialogues: 0."),
                messages);
    }

    @Test
    void reloadRefreshesInteractionsAndDialogueContent() {
        InMemoryEntityInteractionRepository interactionRepository = new InMemoryEntityInteractionRepository();
        InMemoryNpcDialogueRepository dialogueRepository = dialogueRepository();
        NpcDialogueAdminRunner runner = runnerWith(interactionRepository, dialogueRepository);
        List<String> messages = new ArrayList<>();

        runner.reload(messages::add);

        assertEquals(List.of("NPC dialogue content reloaded: 0 binding(s), 1 dialogue file(s)."), messages);
    }

    private static NpcDialogueAdminRunner runnerWith(
            InMemoryEntityInteractionRepository interactionRepository,
            InMemoryNpcDialogueRepository dialogueRepository) {
        return runnerWith(interactionRepository, dialogueRepository, new RecordingAdapterLogger());
    }

    private static NpcDialogueAdminRunner runnerWith(
            InMemoryEntityInteractionRepository interactionRepository,
            InMemoryNpcDialogueRepository dialogueRepository,
            RecordingAdapterLogger logger) {
        return new NpcDialogueAdminRunner(
                new EntityInteractionRegistry(interactionRepository),
                new NpcDialogueRegistry(dialogueRepository),
                new NpcDialogueAdminMessages(),
                logger);
    }

    private static InMemoryNpcDialogueRepository dialogueRepository() {
        return dialogueRepository(Map.of("old-man", dialogue("old-man")));
    }

    private static InMemoryNpcDialogueRepository dialogueRepository(Map<String, NpcDialogueDefinition> dialogues) {
        return new InMemoryNpcDialogueRepository(dialogues);
    }

    private static NpcDialogueDefinition dialogue(String id) {
        return new NpcDialogueDefinition(
                id,
                "初入凡尘",
                "老村民",
                List.of("§6§l任务开始", "§e初入凡尘"),
                List.of("年轻人，你身上有一股未定的气。"),
                30,
                "entity.villager.ambient",
                1.0f);
    }

    private static EntityInteractionEntity interactionEntity(String worldName, String entityUuid, String entityType) {
        return new EntityInteractionEntity(binding(worldName, entityUuid), entityType);
    }

    private static EntityBinding binding(String worldName, String entityUuid) {
        return new EntityBinding(worldName, UUID.fromString(entityUuid));
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

        void replaceWith(List<EntityInteractionDefinition> interactions) {
            this.interactions = new ArrayList<>(interactions);
        }
    }

    private static final class InMemoryNpcDialogueRepository implements NpcDialogueRepository {
        private final Map<String, NpcDialogueDefinition> dialogues;

        private InMemoryNpcDialogueRepository(Map<String, NpcDialogueDefinition> dialogues) {
            this.dialogues = Map.copyOf(dialogues);
        }

        @Override
        public Map<String, NpcDialogueDefinition> loadAll() {
            return dialogues;
        }

        Optional<NpcDialogueDefinition> find(String dialogueId) {
            return Optional.ofNullable(dialogues.get(dialogueId));
        }
    }
}
