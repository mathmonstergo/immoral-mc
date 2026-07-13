package com.immortalmc.adapter;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class PluginResourceTest {
    @Test
    void pluginYmlDeclaresPaperEntrypointCommandAndRuntimeLibraries() throws Exception {
        String pluginYml = readResource("plugin.yml");

        assertTrue(pluginYml.contains("name: ImmortalMC"));
        assertTrue(pluginYml.contains("main: com.immortalmc.adapter.ImmortalMainPlugin"));
        assertTrue(pluginYml.contains("api-version: '1.21.11'"));
        assertTrue(pluginYml.contains("immortal:"));
        assertTrue(pluginYml.contains("usage: /immortal <health|spirit-root|spirit-root-detector|npc-dialogue>"));
        assertTrue(pluginYml.contains("com.fasterxml.jackson.core:jackson-databind:2.18.2"));
    }

    @Test
    void configYmlDeclaresDefaultGameServiceBaseUrl() throws Exception {
        String configYml = readResource("config.yml");

        assertTrue(configYml.contains("game-service:"));
        assertTrue(configYml.contains("base-url: \"http://127.0.0.1:8000\""));
        assertTrue(configYml.contains("entity-interactions:"));
        assertTrue(configYml.contains("entries: []"));
        assertTrue(configYml.contains("scan-interval-ticks: 10"));
        assertTrue(configYml.contains("proximity-radius: 6.0"));
        assertTrue(configYml.contains("max-players-per-scan: 100"));
    }

    @Test
    void exampleDialogueYmlDeclaresNpcDialogueShape() throws Exception {
        String dialogueYml = readResource("dialogues/old-man.yml");

        assertTrue(dialogueYml.contains("id: old-man"));
        assertTrue(dialogueYml.contains("title: \"初入凡尘\""));
        assertTrue(dialogueYml.contains("speaker: \"老村民\""));
        assertTrue(dialogueYml.contains("line-delay-ticks: 30"));
        assertTrue(dialogueYml.contains("sound: \"entity.villager.ambient\""));
        assertTrue(dialogueYml.contains("opening-lines:"));
        assertTrue(dialogueYml.contains("lines:"));
    }

    private static String readResource(String path) throws IOException {
        try (InputStream input = PluginResourceTest.class.getClassLoader().getResourceAsStream(path)) {
            if (input == null) {
                throw new IOException("Missing resource: " + path);
            }
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
