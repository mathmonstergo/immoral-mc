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
        assertTrue(pluginYml.contains("usage: /immortal health"));
        assertTrue(pluginYml.contains("com.fasterxml.jackson.core:jackson-databind:2.18.2"));
    }

    @Test
    void configYmlDeclaresDefaultGameServiceBaseUrl() throws Exception {
        String configYml = readResource("config.yml");

        assertTrue(configYml.contains("game-service:"));
        assertTrue(configYml.contains("base-url: \"http://127.0.0.1:8000\""));
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
