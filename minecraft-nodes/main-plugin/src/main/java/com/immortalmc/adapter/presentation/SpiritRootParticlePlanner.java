package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import java.util.List;
import java.util.Locale;
import java.util.Objects;

public final class SpiritRootParticlePlanner {
    public SpiritRootParticlePlan plan(SpiritRootSnapshot root) {
        Objects.requireNonNull(root, "root");

        return switch (root.quality().toLowerCase(Locale.ROOT)) {
            case "celestial" -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.CELESTIAL_COLUMN,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    64,
                    96);
            case "variant" -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.VARIANT_SURGE,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    48,
                    72);
            case "dual" -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.DUAL_ORBIT,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    36,
                    54);
            case "triple" -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.TRIPLE_FLOW,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    42,
                    60);
            case "quad", "penta" -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.PSEUDO_MIST,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    28,
                    42);
            default -> new SpiritRootParticlePlan(
                    SpiritRootParticleStyle.DEFAULT_AURA,
                    List.copyOf(root.elements()),
                    root.variantElement(),
                    32,
                    48);
        };
    }
}
