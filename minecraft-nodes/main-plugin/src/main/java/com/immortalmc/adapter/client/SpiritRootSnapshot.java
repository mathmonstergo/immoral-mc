package com.immortalmc.adapter.client;

import java.util.List;

public record SpiritRootSnapshot(
        String quality, String label, List<String> elements, String mutatedElement, String variantElement) {}
