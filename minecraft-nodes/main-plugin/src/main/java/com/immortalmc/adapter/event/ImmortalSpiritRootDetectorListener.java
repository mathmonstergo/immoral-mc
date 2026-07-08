package com.immortalmc.adapter.event;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.SpiritRootDetectorRegistry;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionUseCase;
import com.immortalmc.adapter.presentation.SpiritRootParticlePresenter;
import java.util.Objects;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerInteractEntityEvent;
import org.bukkit.inventory.EquipmentSlot;

public final class ImmortalSpiritRootDetectorListener implements Listener {
    private static final String LOG_EVENT_PREFIX = "spirit_root_detector";

    private final SpiritRootDetectorRegistry registry;
    private final SpiritRootDetectionUseCase detectionUseCase;
    private final SpiritRootParticlePresenter particlePresenter;

    public ImmortalSpiritRootDetectorListener(
            SpiritRootDetectorRegistry registry,
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter) {
        this.registry = Objects.requireNonNull(registry, "registry");
        this.detectionUseCase = Objects.requireNonNull(detectionUseCase, "detectionUseCase");
        this.particlePresenter = Objects.requireNonNull(particlePresenter, "particlePresenter");
    }

    @EventHandler(ignoreCancelled = true)
    public void onPlayerInteractEntity(PlayerInteractEntityEvent event) {
        if (event.getHand() != EquipmentSlot.HAND) {
            return;
        }

        Entity detector = event.getRightClicked();
        EntityBinding binding = new EntityBinding(detector.getWorld().getName(), detector.getUniqueId());
        if (!registry.matches(binding)) {
            return;
        }

        event.setCancelled(true);
        Player player = event.getPlayer();
        detectionUseCase.detectForPlayer(
                player.getUniqueId(),
                LOG_EVENT_PREFIX,
                player::sendMessage,
                result -> particlePresenter.play(player, detector, result.spiritRoot()));
    }
}
