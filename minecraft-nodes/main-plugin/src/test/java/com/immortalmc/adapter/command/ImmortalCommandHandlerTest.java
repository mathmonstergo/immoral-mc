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
    void spiritRootDetectorReloadSubcommandReloadsDetectorContent() {
        ImmortalCommandHandler handler = new ImmortalCommandHandler();

        assertEquals(
                ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_RELOAD,
                handler.resolve(new String[] {"spirit-root-detector", "reload"}));
    }
}
