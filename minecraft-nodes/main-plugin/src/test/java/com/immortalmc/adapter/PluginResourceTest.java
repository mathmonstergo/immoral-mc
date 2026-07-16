package com.immortalmc.adapter;

import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import javax.imageio.ImageIO;
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
        assertTrue(pluginYml.contains("- BetterHud"));
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

    @Test
    void packagedBetterHudResourcesDeclareTwoAuthoritativeBars() throws Exception {
        String images = readResource("betterhud/images/immortal-cultivation.yml");
        String layouts = readResource("betterhud/layouts/immortal-cultivation.yml");
        String huds = readResource("betterhud/huds/immortal-cultivation.yml");
        String texts = readResource("betterhud/texts/immortal-cultivation.yml");

        assertTrue(images.contains("immortal_main_fill:"));
        assertTrue(images.contains("value: immortal_current"));
        assertTrue(images.contains("max: immortal_max"));
        assertTrue(images.contains("immortal_reserve_fill:"));
        assertTrue(images.contains("value: immortal_reserve"));
        assertTrue(images.contains("max: immortal_reserve_cap"));
        assertTrue(layouts.contains("pattern: \"[immortal_realm_name]\""));
        assertTrue(layouts.contains("name: immortal_cultivation_font"));
        assertTrue(layouts.contains("name: immortal_main_empty"));
        assertTrue(layouts.contains("name: immortal_reserve_empty"));
        assertTrue(huds.contains("immortal_cultivation:"));
        assertTrue(huds.contains("name: immortal_cultivation_layout"));
        assertTrue(texts.contains("immortal_cultivation_font:"));
        assertTrue(texts.contains("use-unifont: true"));
    }

    @Test
    void packagedBetterHudTexturesHaveMinimalExpectedDimensionsAndAlpha() throws Exception {
        assertPng("betterhud/assets/immortal/main-empty.png", 180, 8);
        assertPng("betterhud/assets/immortal/main-fill.png", 180, 8);
        assertPng("betterhud/assets/immortal/reserve-empty.png", 180, 3);
        assertPng("betterhud/assets/immortal/reserve-fill.png", 180, 3);
    }

    private static void assertPng(String path, int width, int height) throws IOException {
        try (InputStream input = PluginResourceTest.class.getClassLoader().getResourceAsStream(path)) {
            if (input == null) {
                throw new IOException("Missing resource: " + path);
            }
            var image = ImageIO.read(input);
            assertTrue(image != null);
            assertTrue(image.getColorModel().hasAlpha());
            assertTrue(image.getWidth() == width);
            assertTrue(image.getHeight() == height);
        }
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
