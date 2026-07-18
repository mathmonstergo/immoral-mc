package com.immortalmc.adapter.presentation;

import io.papermc.paper.scoreboard.numbers.NumberFormat;
import java.util.ArrayList;
import java.util.List;
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
    private static final String HINT_ENTRY = "§f";
    private static final int MAX_OBJECTIVES = 12;
    private static final String[] OBJECTIVE_ENTRIES = {
        "§1", "§2", "§3", "§4", "§5", "§6",
        "§7", "§8", "§9", "§a", "§b", "§c"
    };

    private final Player player;
    private final Scoreboard previous;
    private final Scoreboard scoreboard;
    private final Team questTeam;
    private final Objective sidebar;
    private final List<Team> objectiveTeams = new ArrayList<>();
    private final Team hintTeam;
    private boolean hidden;

    public BukkitQuestScoreboardView(Player player) {
        this(player, Bukkit.getScoreboardManager(), NumberFormat.blank());
    }

    BukkitQuestScoreboardView(Player player, ScoreboardManager manager, NumberFormat numberFormat) {
        this.player = Objects.requireNonNull(player, "player");
        Objects.requireNonNull(manager, "scoreboardManager");
        Objects.requireNonNull(numberFormat, "numberFormat");
        previous = player.getScoreboard();
        scoreboard = manager.getNewScoreboard();
        sidebar = scoreboard.registerNewObjective(
                "immortal_quest",
                "dummy",
                Component.text("修仙纪事", NamedTextColor.GOLD));
        sidebar.numberFormat(numberFormat);
        sidebar.setDisplaySlot(DisplaySlot.SIDEBAR);
        questTeam = registerLine("quest_title", QUEST_ENTRY, MAX_OBJECTIVES + 2, sidebar);
        hintTeam = registerLine("quest_hint", HINT_ENTRY, 1, sidebar);
        player.setScoreboard(scoreboard);
    }

    @Override
    public void setQuestTitle(String value) {
        questTeam.prefix(Component.text(value, NamedTextColor.YELLOW));
    }

    @Override
    public void setObjectives(List<String> values) {
        List<String> objectiveLines = List.copyOf(values);
        if (objectiveLines.size() > MAX_OBJECTIVES) {
            throw new IllegalArgumentException("Quest scoreboard supports at most 12 objectives");
        }
        for (int index = 0; index < objectiveLines.size(); index++) {
            Team team;
            if (index < objectiveTeams.size()) {
                team = objectiveTeams.get(index);
            } else {
                team = registerLine(
                        "quest_objective_" + index,
                        OBJECTIVE_ENTRIES[index],
                        MAX_OBJECTIVES + 1 - index,
                        sidebar);
                objectiveTeams.add(team);
            }
            team.prefix(Component.text(objectiveLines.get(index), NamedTextColor.WHITE));
        }
        while (objectiveTeams.size() > objectiveLines.size()) {
            int last = objectiveTeams.size() - 1;
            Team removed = objectiveTeams.remove(last);
            scoreboard.resetScores(OBJECTIVE_ENTRIES[last]);
            removed.unregister();
        }
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
