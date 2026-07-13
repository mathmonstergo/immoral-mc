package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class ImmortalCommandHandlerTest {
    @Test
    void noSubcommandShowsUsage() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(ImmortalCommandAction.USAGE, handler.resolve(new String[] {}));
    }

    @Test
    void healthSubcommandRunsHealthCheck() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(ImmortalCommandAction.HEALTH, handler.resolve(new String[] {"health"}));
    }

    @Test
    void spiritRootSubcommandRunsSpiritRootDetection() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(ImmortalCommandAction.SPIRIT_ROOT, handler.resolve(new String[] {"spirit-root"}));
    }

    @Test
    void spiritRootDetectorSetSubcommandSavesDetectorEntity() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_SET,
                handler.resolve(new String[] {"spirit-root-detector", "set"}));
    }

    @Test
    void spiritRootDetectorCreateSubcommandCreatesDetectorEntity() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_CREATE,
                handler.resolve(new String[] {"spirit-root-detector", "create"}));
    }

    @Test
    void spiritRootDetectorListSubcommandListsDetectorEntities() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_LIST,
                handler.resolve(new String[] {"spirit-root-detector", "list"}));
    }

    @Test
    void spiritRootDetectorRemoveSubcommandRemovesDetectorEntityBinding() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_REMOVE,
                handler.resolve(new String[] {"spirit-root-detector", "remove"}));
    }

    @Test
    void spiritRootDetectorReloadSubcommandReloadsDetectorContent() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_RELOAD,
                handler.resolve(new String[] {"spirit-root-detector", "reload"}));
    }

    @Test
    void npcDialogueSetSubcommandBindsLookedAtEntity() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.NPC_DIALOGUE_SET,
                handler.resolve(new String[] {"npc-dialogue", "set", "old-man"}));
    }

    @Test
    void npcDialogueListSubcommandListsBindings() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.NPC_DIALOGUE_LIST,
                handler.resolve(new String[] {"npc-dialogue", "list"}));
    }

    @Test
    void npcDialogueRemoveSubcommandRemovesBinding() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.NPC_DIALOGUE_REMOVE,
                handler.resolve(new String[] {"npc-dialogue", "remove"}));
    }

    @Test
    void npcDialogueReloadSubcommandReloadsBindingsAndYamlContent() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.NPC_DIALOGUE_RELOAD,
                handler.resolve(new String[] {"npc-dialogue", "reload"}));
    }

    @Test
    void questSubcommandsResolveExactAuthoringCommandFamily() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.QUEST_TEMPLATES,
                handler.resolve(new String[] {"quest", "templates"}));
        assertEquals(
                ImmortalCommandAction.QUEST_BIND,
                handler.resolve(new String[] {"quest", "bind", "old-man"}));
        assertEquals(ImmortalCommandAction.QUEST_INFO, handler.resolve(new String[] {"quest", "info"}));
        assertEquals(ImmortalCommandAction.QUEST_LIST, handler.resolve(new String[] {"quest", "list"}));
        assertEquals(ImmortalCommandAction.QUEST_UNBIND, handler.resolve(new String[] {"quest", "unbind"}));
        assertEquals(ImmortalCommandAction.QUEST_RELOAD, handler.resolve(new String[] {"quest", "reload"}));
        assertEquals(
                ImmortalCommandAction.USAGE,
                handler.resolve(new String[] {"quest", "bind"}));
    }
}
