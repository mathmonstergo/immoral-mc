package com.immortalmc.adapter.config;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.net.URI;
import org.junit.jupiter.api.Test;

class PluginSettingsTest {
    @Test
    void usesConfiguredGameServiceBaseUrl() {
        PluginSettings settings = PluginSettings.from("http://127.0.0.1:8000");

        assertEquals(URI.create("http://127.0.0.1:8000"), settings.gameServiceBaseUri());
    }
}
