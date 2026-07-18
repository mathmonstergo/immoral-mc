package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import io.papermc.paper.scoreboard.numbers.NumberFormat;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.IntStream;
import org.bukkit.entity.Player;
import org.bukkit.scoreboard.Objective;
import org.bukkit.scoreboard.Score;
import org.bukkit.scoreboard.Scoreboard;
import org.bukkit.scoreboard.ScoreboardManager;
import org.bukkit.scoreboard.Team;
import org.junit.jupiter.api.Test;

class BukkitQuestScoreboardViewTest {
    @Test
    void appliesBlankNumberFormatToSidebarObjective() {
        NumberFormat blank = proxy(NumberFormat.class, (method, args) -> null);
        AtomicReference<NumberFormat> applied = new AtomicReference<>();
        Score score = proxy(Score.class, (method, args) -> null);
        Objective objective = proxy(Objective.class, (method, args) -> {
            if (method.equals("getScore")) {
                return score;
            }
            if (method.equals("numberFormat") && args != null && args.length == 1) {
                applied.set((NumberFormat) args[0]);
            }
            return null;
        });
        Team team = proxy(Team.class, (method, args) -> null);
        Scoreboard previous = proxy(Scoreboard.class, (method, args) -> null);
        Scoreboard scoreboard = proxy(Scoreboard.class, (method, args) -> switch (method) {
            case "registerNewObjective" -> objective;
            case "registerNewTeam" -> team;
            default -> null;
        });
        ScoreboardManager manager = proxy(
                ScoreboardManager.class,
                (method, args) -> method.equals("getNewScoreboard") ? scoreboard : previous);
        Player player = proxy(Player.class, (method, args) -> method.equals("getScoreboard") ? previous : null);

        new BukkitQuestScoreboardView(player, manager, blank);

        assertSame(blank, applied.get());
    }

    @Test
    void rendersTwelveUniqueRowsAndRemovesStaleObjectiveTeams() {
        Map<String, Integer> scores = new HashMap<>();
        List<String> resetEntries = new ArrayList<>();
        Set<String> unregisteredTeams = new HashSet<>();
        Objective objective = proxy(Objective.class, (method, args) -> {
            if (method.equals("getScore")) {
                String entry = (String) args[0];
                return proxy(Score.class, (scoreMethod, scoreArgs) -> {
                    if (scoreMethod.equals("setScore")) {
                        scores.put(entry, (Integer) scoreArgs[0]);
                    }
                    return null;
                });
            }
            return null;
        });
        Scoreboard previous = proxy(Scoreboard.class, (method, args) -> null);
        Scoreboard scoreboard = proxy(Scoreboard.class, (method, args) -> {
            if (method.equals("registerNewObjective")) {
                return objective;
            }
            if (method.equals("registerNewTeam")) {
                String name = (String) args[0];
                return proxy(Team.class, (teamMethod, teamArgs) -> {
                    if (teamMethod.equals("unregister")) {
                        unregisteredTeams.add(name);
                    }
                    return null;
                });
            }
            if (method.equals("resetScores")) {
                resetEntries.add((String) args[0]);
            }
            return null;
        });
        ScoreboardManager manager = proxy(
                ScoreboardManager.class,
                (method, args) -> method.equals("getNewScoreboard") ? scoreboard : previous);
        Player player = proxy(
                Player.class,
                (method, args) -> method.equals("getScoreboard") ? previous : null);
        BukkitQuestScoreboardView view = new BukkitQuestScoreboardView(
                player,
                manager,
                proxy(NumberFormat.class, (method, args) -> null));

        view.setObjectives(IntStream.rangeClosed(1, 12).mapToObj(index -> "目标" + index).toList());

        assertEquals(14, scores.size());
        assertEquals(
                IntStream.rangeClosed(1, 14).boxed().collect(java.util.stream.Collectors.toSet()),
                new HashSet<>(scores.values()));
        view.setObjectives(List.of("保留目标"));
        assertEquals(11, resetEntries.size());
        assertEquals(11, unregisteredTeams.size());
        assertThrows(
                IllegalArgumentException.class,
                () -> view.setObjectives(IntStream.rangeClosed(1, 13)
                        .mapToObj(index -> "超限" + index)
                        .toList()));
    }

    @SuppressWarnings("unchecked")
    private static <T> T proxy(Class<T> type, Handler handler) {
        return (T) Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> {
                    Object value = handler.invoke(method.getName(), args);
                    return value != null ? value : defaultValue(method.getReturnType());
                });
    }

    private static Object defaultValue(Class<?> type) {
        if (!type.isPrimitive()) {
            return null;
        }
        if (type == boolean.class) {
            return false;
        }
        return 0;
    }

    @FunctionalInterface
    private interface Handler {
        Object invoke(String method, Object[] args);
    }
}
