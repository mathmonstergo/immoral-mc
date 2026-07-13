package com.immortalmc.adapter.presentation;

import java.util.Objects;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.scoreboard.DisplaySlot;
import org.bukkit.scoreboard.Objective;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.ScoreboardManager;
import org.bukkit.scoreboard.Team;

public final class BukkitQuestScoreboardView implements QuestScoreboardView {
    private static final String QUEST_ENTRY = "§0";
    private static final String OBJECTIVE_ENTRY = "§1";
    private static final String HINT_ENTRY = "§2";

    private final Player player;
    private final Scoreboard previous;
    private final Scoreboard scoreboard;
    private final Team questTeam;
    private final Team objectiveTeam;
    private final Team hintTeam;
    private boolean hidden;

    public BukkitQuestScoreboardView(Player player) {
        this.player = Objects.requireNonNull(player, "player");
        ScoreboardManager manager = Objects.requireNonNull(Bukkit.getScoreboardManager(), "scoreboardManager");
        previous = player.getScoreboard();
        scoreboard = manager.getNewScoreboard();
        Objective objective = scoreboard.registerNewObjective(
                "immortal_quest",
                "dummy",
                Component.text("修仙纪事", NamedTextColor.GOLD));
        objective.setDisplaySlot(DisplaySlot.SIDEBAR);
        questTeam = registerLine("quest_title", QUEST_ENTRY, 3, objective);
        objectiveTeam = registerLine("quest_objective", OBJECTIVE_ENTRY, 2, objective);
        hintTeam = registerLine("quest_hint", HINT_ENTRY, 1, objective);
        player.setScoreboard(scoreboard);
    }

    @Override
    public void setQuestTitle(String value) {
        questTeam.prefix(Component.text(value, NamedTextColor.YELLOW));
    }

    @Override
    public void setObjective(String value) {
        objectiveTeam.prefix(Component.text(value, NamedTextColor.WHITE));
    }

    @Override
    public void setHint(String value) {
        hintTeam.prefix(Component.text(value, NamedTextColor.GRAY));
    }

    @Override
    public void hide() {
        if (!hidden) {
            hidden = true;
            if (player.isOnline() && player.getScoreboard() == scoreboard) {
                player.setScoreboard(previous);
            }
        }
    }

    private Team registerLine(String name, String entry, int score, Objective objective) {
        Team team = scoreboard.registerNewTeam(name);
        team.addEntry(entry);
        objective.getScore(entry).setScore(score);
        return team;
    }
}
