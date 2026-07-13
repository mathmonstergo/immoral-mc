package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import org.bukkit.entity.Player;

@FunctionalInterface
public interface SpiritRootTitlePresenter {
    void show(Player player, SpiritRootSnapshot spiritRoot);
}
