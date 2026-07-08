package com.immortalmc.adapter.config;

import java.net.URI;

public record PluginSettings(URI gameServiceBaseUri) {
    public static PluginSettings from(String gameServiceBaseUrl) {
        return new PluginSettings(URI.create(gameServiceBaseUrl));
    }
}
