package com.immortalmc.adapter;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;

class PluginResourceTest {
    @Test
    void pluginYmlDeclaresPaperEntrypointCommandAndRuntimeLibraries() throws Exception {
        String pluginYml = readResource("plugin.yml");

        assertTrue(pluginYml.contains("name: ImmortalMC"));
        assertTrue(pluginYml.contains("main: com.immortalmc.adapter.ImmortalMainPlugin"));
        assertTrue(pluginYml.contains("api-version: '1.21.11'"));
        assertTrue(pluginYml.contains("immortal:"));
        assertTrue(pluginYml.contains(
                "usage: /immortal <health|spirit-root|spirit-root-detector|npc-dialogue|quest>"));
        assertTrue(pluginYml.contains("com.fasterxml.jackson.core:jackson-databind:2.18.2"));
        assertTrue(pluginYml.contains("org.xerial:sqlite-jdbc:3.53.2.0"));
        assertTrue(pluginYml.contains("- MythicMobs"));
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
        assertTrue(configYml.contains("server-id: \"main-1\""));
        assertTrue(configYml.contains("max-source-age-seconds: 900"));
        assertTrue(configYml.contains("max-active-targets: 20000"));
        assertTrue(configYml.contains("normal-interval-ms: 1000"));
        assertTrue(configYml.contains("high-load-interval-ms: 5000"));
        assertTrue(configYml.contains("batch-size: 100"));
        assertTrue(configYml.contains("max-pending-age-seconds: 30"));
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

    @Test
    void buildUsesOfficialFreeMythicApiWithoutLocalOrPremiumArtifacts() throws Exception {
        String build = Files.readString(Path.of("build.gradle.kts"), StandardCharsets.UTF_8);

        assertTrue(build.contains("io.lumine:Mythic-Dist:5.12.1"));
        assertTrue(!build.contains("Premium"));
        assertTrue(!build.contains("plugins-new-add"));
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
