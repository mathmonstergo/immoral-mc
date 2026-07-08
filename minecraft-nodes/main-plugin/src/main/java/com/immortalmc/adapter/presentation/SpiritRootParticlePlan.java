package com.immortalmc.adapter.presentation;

import java.util.List;

public record SpiritRootParticlePlan(
        SpiritRootParticleStyle style,
        List<String> elements,
        String variantElement,
        int playerParticleCount,
        int detectorParticleCount) {}
