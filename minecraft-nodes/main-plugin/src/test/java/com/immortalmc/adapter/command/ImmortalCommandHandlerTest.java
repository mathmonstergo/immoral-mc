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
}
