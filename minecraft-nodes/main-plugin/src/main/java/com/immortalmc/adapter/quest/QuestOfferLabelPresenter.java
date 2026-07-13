package com.immortalmc.adapter.quest;

import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

@FunctionalInterface
public interface QuestOfferLabelPresenter {
    QuestOfferLabel show(Player player, Entity npc);
}
