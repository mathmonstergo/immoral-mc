package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.lang.reflect.Proxy;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.entity.TextDisplay;
import org.bukkit.plugin.Plugin;
import org.junit.jupiter.api.Test;

class BukkitQuestOfferLabelPresenterTest {
    @Test
    void spawnsPrivateStatusAboveCitizensNameplate() {
        Plugin plugin = proxy(Plugin.class, (method, args) -> null);
        TextDisplay display = proxy(TextDisplay.class, (method, args) -> method.equals("isValid"));
        AtomicReference<Location> spawnedAt = new AtomicReference<>();
        World world = proxy(World.class, (method, args) -> {
            if (method.equals("spawn")) {
                spawnedAt.set(((Location) args[0]).clone());
                @SuppressWarnings("unchecked")
                Consumer<TextDisplay> initializer = (Consumer<TextDisplay>) args[2];
                initializer.accept(display);
                return display;
            }
            return null;
        });
        Entity npc = proxy(Entity.class, (method, args) -> switch (method) {
            case "getWorld" -> world;
            case "getLocation" -> new Location(world, 4.0, 64.0, 8.0);
            case "getHeight" -> 1.8;
            default -> null;
        });
        AtomicReference<Entity> shown = new AtomicReference<>();
        Player player = proxy(Player.class, (method, args) -> {
            if (method.equals("showEntity")) {
                assertSame(plugin, args[0]);
                shown.set((Entity) args[1]);
            }
            return null;
        });

        new BukkitQuestOfferLabelPresenter(plugin).show(player, npc);

        assertEquals(66.7, spawnedAt.get().getY(), 0.0001);
        assertSame(display, shown.get());
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
        if (type == double.class) {
            return 0.0;
        }
        return 0;
    }

    @FunctionalInterface
    private interface Handler {
        Object invoke(String method, Object[] args);
    }
}
