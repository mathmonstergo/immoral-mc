package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import java.util.Objects;
import org.bukkit.Location;
import org.bukkit.Particle;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public final class BukkitSpiritRootParticlePresenter implements SpiritRootParticlePresenter {
    private final SpiritRootParticlePlanner planner;

    public BukkitSpiritRootParticlePresenter(SpiritRootParticlePlanner planner) {
        this.planner = Objects.requireNonNull(planner, "planner");
    }

    @Override
    public void play(Player player, Entity detector, SpiritRootSnapshot root) {
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(detector, "detector");
        Objects.requireNonNull(root, "root");

        SpiritRootParticlePlan plan = planner.plan(root);
        Particle styleParticle = particleFor(plan.style());
        Particle elementParticle = particleForFirstElement(plan);
        Location playerLocation = player.getLocation().clone().add(0.0, 1.0, 0.0);
        Location detectorLocation = detector.getLocation().clone().add(0.0, Math.max(0.8, detector.getHeight() * 0.6), 0.0);

        player.getWorld().spawnParticle(
                elementParticle,
                playerLocation,
                plan.playerParticleCount(),
                0.8,
                0.9,
                0.8,
                0.02);
        detector.getWorld().spawnParticle(
                styleParticle,
                detectorLocation,
                plan.detectorParticleCount(),
                0.7,
                1.0,
                0.7,
                0.03);
    }

    private Particle particleFor(SpiritRootParticleStyle style) {
        return switch (style) {
            case CELESTIAL_COLUMN -> Particle.END_ROD;
            case VARIANT_SURGE -> Particle.WITCH;
            case DUAL_ORBIT -> Particle.ENCHANT;
            case TRIPLE_FLOW -> Particle.HAPPY_VILLAGER;
            case PSEUDO_MIST -> Particle.CLOUD;
            case DEFAULT_AURA -> Particle.ENCHANT;
        };
    }

    private Particle particleForFirstElement(SpiritRootParticlePlan plan) {
        if (plan.variantElement() != null) {
            return particleForVariantElement(plan.variantElement());
        }
        if (plan.elements().isEmpty()) {
            return Particle.ENCHANT;
        }
        return switch (plan.elements().get(0)) {
            case "火", "fire" -> Particle.FLAME;
            case "水", "water" -> Particle.SPLASH;
            case "木", "wood" -> Particle.HAPPY_VILLAGER;
            case "金", "metal" -> Particle.END_ROD;
            case "土", "earth" -> Particle.CLOUD;
            default -> Particle.ENCHANT;
        };
    }

    private Particle particleForVariantElement(String variantElement) {
        return switch (variantElement) {
            case "雷" -> Particle.CRIT;
            case "冰" -> Particle.SNOWFLAKE;
            case "风" -> Particle.CLOUD;
            case "暗" -> Particle.WITCH;
            default -> Particle.WITCH;
        };
    }
}
