package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import java.util.List;
import org.junit.jupiter.api.Test;

class SpiritRootParticlePlannerTest {
    @Test
    void celestialRootUsesCelestialColumnStyle() {
        SpiritRootParticlePlan plan = new SpiritRootParticlePlanner()
                .plan(new SpiritRootSnapshot("celestial", "天灵根", List.of("火"), null, null));

        assertEquals(SpiritRootParticleStyle.CELESTIAL_COLUMN, plan.style());
        assertEquals(List.of("火"), plan.elements());
        assertEquals(64, plan.playerParticleCount());
        assertEquals(96, plan.detectorParticleCount());
    }

    @Test
    void variantRootPreservesVariantElementAndUsesVariantSurgeStyle() {
        SpiritRootParticlePlan plan = new SpiritRootParticlePlanner()
                .plan(new SpiritRootSnapshot("variant", "异灵根", List.of("金"), "金雷", "雷"));

        assertEquals(SpiritRootParticleStyle.VARIANT_SURGE, plan.style());
        assertEquals(List.of("金"), plan.elements());
        assertEquals("雷", plan.variantElement());
    }

    @Test
    void rootQualitiesMapToDifferentVisibleStyles() {
        SpiritRootParticlePlanner planner = new SpiritRootParticlePlanner();

        SpiritRootParticleStyle celestial = planner
                .plan(new SpiritRootSnapshot("celestial", "天灵根", List.of("水"), null, null))
                .style();
        SpiritRootParticleStyle dual = planner
                .plan(new SpiritRootSnapshot("dual", "双灵根", List.of("水", "火"), null, null))
                .style();
        SpiritRootParticleStyle triple = planner
                .plan(new SpiritRootSnapshot("triple", "三灵根", List.of("金", "木", "土"), null, null))
                .style();
        SpiritRootParticleStyle pseudo = planner
                .plan(new SpiritRootSnapshot("penta", "伪灵根", List.of("金", "木", "水", "火", "土"), null, null))
                .style();

        assertNotEquals(celestial, dual);
        assertNotEquals(dual, triple);
        assertNotEquals(triple, pseudo);
    }
}
