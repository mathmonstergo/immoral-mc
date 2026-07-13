package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.quest.QuestOfferLabel;
import com.immortalmc.adapter.quest.QuestOfferLabelPresenter;
import java.util.Objects;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Location;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.plugin.java.JavaPlugin;

public final class BukkitQuestOfferLabelPresenter implements QuestOfferLabelPresenter {
    private final JavaPlugin plugin;

    public BukkitQuestOfferLabelPresenter(JavaPlugin plugin) {
        this.plugin = Objects.requireNonNull(plugin, "plugin");
    }

    @Override
    public QuestOfferLabel show(Player player, Entity npc) {
        Objects.requireNonNull(player, "player");
        Objects.requireNonNull(npc, "npc");
        Location location = npc.getLocation().add(0.0, npc.getHeight() + 0.35, 0.0);
        TextDisplay display = npc.getWorld().spawn(location, TextDisplay.class, entity -> {
            entity.text(Component.text("任务接取中...", NamedTextColor.YELLOW));
            entity.setBillboard(Display.Billboard.CENTER);
            entity.setAlignment(TextDisplay.TextAlignment.CENTER);
            entity.setShadowed(true);
            entity.setSeeThrough(true);
            entity.setGravity(false);
            entity.setInvulnerable(true);
            entity.setPersistent(false);
            entity.setVisibleByDefault(false);
        });
        player.showEntity(plugin, display);
        return new DisplayLabel(display);
    }

    private static final class DisplayLabel implements QuestOfferLabel {
        private final TextDisplay display;
        private boolean removed;

        private DisplayLabel(TextDisplay display) {
            this.display = display;
        }

        @Override
        public void showAwaitingConfirmation() {
            if (!removed && display.isValid()) {
                display.text(Component.text("右键接取任务", NamedTextColor.GREEN));
            }
        }

        @Override
        public void remove() {
            if (!removed) {
                removed = true;
                display.remove();
            }
        }
    }
}
