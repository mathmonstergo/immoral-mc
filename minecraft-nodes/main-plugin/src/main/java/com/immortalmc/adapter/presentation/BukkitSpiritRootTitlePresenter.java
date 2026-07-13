package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.SpiritRootSnapshot;
import java.time.Duration;
import java.util.Objects;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.title.Title;
import org.bukkit.entity.Player;

public final class BukkitSpiritRootTitlePresenter implements SpiritRootTitlePresenter {
    @Override
    public void show(Player player, SpiritRootSnapshot spiritRoot) {
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(spiritRoot, "spiritRoot");
        String element = spiritRoot.mutatedElement() != null
                ? spiritRoot.mutatedElement()
                : String.join("·", spiritRoot.elements());
        player.showTitle(Title.title(
                Component.text("灵根觉醒", NamedTextColor.GOLD),
                Component.text(spiritRoot.label() + " · " + element, NamedTextColor.AQUA),
                Title.Times.times(Duration.ofMillis(300), Duration.ofSeconds(3), Duration.ofMillis(600))));
    }
}
