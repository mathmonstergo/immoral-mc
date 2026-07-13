package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.GameServiceException;
import com.immortalmc.adapter.client.HealthCheckResult;
import org.junit.jupiter.api.Test;

class HealthCommandMessagesTest {
    @Test
    void checkingMessageExplainsHealthCheckIsInProgress() {
        HealthCommandMessages messages = new HealthCommandMessages();

        assertEquals("Checking Game Service health...", messages.checking());
    }

    @Test
    void successMessageIncludesServiceStatusAndVersion() {
        HealthCommandMessages messages = new HealthCommandMessages();

        String message = messages.success(new HealthCheckResult("game-service", "ok", "0.1.0"));

        assertEquals("Game Service: game-service ok (0.1.0)", message);
    }

    @Test
    void failureMessageIncludesExceptionMessage() {
        HealthCommandMessages messages = new HealthCommandMessages();

        String message = messages.failure(new GameServiceException("Game Service health check failed with HTTP 503"));

        assertEquals("Game Service unavailable: Game Service health check failed with HTTP 503", message);
    }

    @Test
    void usageMessageShowsSupportedSubcommands() {
        HealthCommandMessages messages = new HealthCommandMessages();

        assertEquals(
                "Usage: /immortal <health|spirit-root|spirit-root-detector|npc-dialogue|quest>",
                messages.usage());
    }
}
