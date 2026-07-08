package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public interface SpiritRootParticlePresenter {
    void play(Player player, Entity detector, SpiritRootSnapshot root);
}
