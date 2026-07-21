package com.immortalmc.adapter.quest;

import java.util.UUID;
import org.bukkit.entity.Player;

@FunctionalInterface
public interface QuestProviderGuiOpener {
    void open(Player player, String interactionId, UUID npcId, String providerId);
}
