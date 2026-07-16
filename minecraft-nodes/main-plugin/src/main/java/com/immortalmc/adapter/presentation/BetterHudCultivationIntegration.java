package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.logging.AdapterLogger;
import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Array;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Function;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.java.JavaPlugin;

public final class BetterHudCultivationIntegration {
    public static final String HUD_NAME = "immortal_cultivation";
    private static final Map<String, String> MANAGED_RESOURCES = Map.of(
            "betterhud/images/immortal-cultivation.yml", "images/immortal-cultivation.yml",
            "betterhud/layouts/immortal-cultivation.yml", "layouts/immortal-cultivation.yml",
            "betterhud/huds/immortal-cultivation.yml", "huds/immortal-cultivation.yml",
            "betterhud/texts/immortal-cultivation.yml", "texts/immortal-cultivation.yml",
            "betterhud/assets/immortal/main-empty.png", "assets/immortal/main-empty.png",
            "betterhud/assets/immortal/main-fill.png", "assets/immortal/main-fill.png",
            "betterhud/assets/immortal/reserve-empty.png", "assets/immortal/reserve-empty.png",
            "betterhud/assets/immortal/reserve-fill.png", "assets/immortal/reserve-fill.png");

    private final CultivationProjectionStore store;
    private final AdapterLogger logger;
    private final Bridge bridge;
    private boolean active;

    BetterHudCultivationIntegration(
            CultivationProjectionStore store,
            AdapterLogger logger,
            Bridge bridge) {
        this.store = Objects.requireNonNull(store, "store");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.bridge = bridge;
    }

    public static BetterHudCultivationIntegration create(
            JavaPlugin plugin,
            CultivationProjectionStore store,
            AdapterLogger logger) {
        Objects.requireNonNull(plugin, "plugin");
        Plugin betterHud = plugin.getServer().getPluginManager().getPlugin("BetterHud");
        Bridge bridge = betterHud != null && betterHud.isEnabled()
                ? new ReflectiveBridge(plugin, betterHud)
                : null;
        return new BetterHudCultivationIntegration(store, logger, bridge);
    }

    public boolean start() {
        if (bridge == null) {
            logger.warn("betterhud_cultivation_unavailable presentation=disabled");
            return false;
        }
        try {
            bridge.installResources();
            bridge.registerString("immortal_realm_name", playerId -> store.snapshot(playerId).realmName());
            bridge.registerNumber("immortal_current", playerId -> store.snapshot(playerId).currentProgress());
            bridge.registerNumber("immortal_max", playerId -> store.snapshot(playerId).maxExp());
            bridge.registerNumber("immortal_current_ratio", playerId -> store.snapshot(playerId).currentRatio());
            bridge.registerNumber("immortal_reserve", playerId -> store.snapshot(playerId).unrefinedReserve());
            bridge.registerNumber("immortal_reserve_cap", playerId -> store.snapshot(playerId).reserveCap());
            bridge.registerNumber("immortal_reserve_ratio", playerId -> store.snapshot(playerId).reserveRatio());
            bridge.reload();
            active = true;
            logger.info("betterhud_cultivation_enabled hud=" + HUD_NAME);
            return true;
        } catch (RuntimeException | LinkageError error) {
            active = false;
            logger.warn("betterhud_cultivation_start_failed presentation=disabled", error);
            return false;
        }
    }

    public void refresh(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        if (!active) {
            return;
        }
        try {
            if (!store.snapshot(playerId).enabled()) {
                bridge.hide(playerId, HUD_NAME);
                return;
            }
            bridge.show(playerId, HUD_NAME);
            bridge.update(playerId);
        } catch (RuntimeException | LinkageError error) {
            logger.warn("betterhud_cultivation_refresh_failed player_uuid=" + playerId, error);
        }
    }

    public void remove(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        if (!active) {
            return;
        }
        try {
            bridge.hide(playerId, HUD_NAME);
        } catch (RuntimeException | LinkageError error) {
            logger.warn("betterhud_cultivation_remove_failed player_uuid=" + playerId, error);
        }
    }

    interface Bridge {
        void installResources();

        void registerString(String name, Function<UUID, String> value);

        void registerNumber(String name, Function<UUID, Number> value);

        void reload();

        void show(UUID playerId, String hudName);

        void update(UUID playerId);

        void hide(UUID playerId, String hudName);
    }

    private static final class ReflectiveBridge implements Bridge {
        private static final String BETTER_HUD_CLASS = "kr.toxicity.hud.api.BetterHud";
        private static final String HUD_PLACEHOLDER_CLASS = "kr.toxicity.hud.api.placeholder.HudPlaceholder";
        private static final String PLACEHOLDER_FUNCTION_CLASS =
                "kr.toxicity.hud.api.placeholder.HudPlaceholder$PlaceholderFunction";
        private static final String RELOAD_FLAG_CLASS = "kr.toxicity.hud.api.plugin.ReloadFlagType";

        private final JavaPlugin resourcePlugin;
        private final Plugin betterHudPlugin;
        private final ClassLoader betterHudClassLoader;

        private ReflectiveBridge(JavaPlugin resourcePlugin, Plugin betterHudPlugin) {
            this.resourcePlugin = resourcePlugin;
            this.betterHudPlugin = betterHudPlugin;
            this.betterHudClassLoader = betterHudPlugin.getClass().getClassLoader();
        }

        @Override
        public void installResources() {
            Path dataFolder = betterHudPlugin.getDataFolder().toPath();
            for (Map.Entry<String, String> resource : MANAGED_RESOURCES.entrySet()) {
                Path target = dataFolder.resolve(resource.getValue());
                try (InputStream input = resourcePlugin.getResource(resource.getKey())) {
                    if (input == null) {
                        throw new IllegalStateException("Missing packaged BetterHud resource: " + resource.getKey());
                    }
                    Files.createDirectories(target.getParent());
                    Files.copy(input, target, StandardCopyOption.REPLACE_EXISTING);
                } catch (IOException error) {
                    throw new IllegalStateException("Unable to install BetterHud resource: " + resource.getKey(), error);
                }
            }
        }

        @Override
        public void registerString(String name, Function<UUID, String> value) {
            registerPlaceholder("getStringContainer", name, value);
        }

        @Override
        public void registerNumber(String name, Function<UUID, Number> value) {
            registerPlaceholder("getNumberContainer", name, value);
        }

        @Override
        public void reload() {
            Object instance = instance();
            Class<?> flagType = type(RELOAD_FLAG_CLASS);
            Object flags = Array.newInstance(flagType, 0);
            Object state = invoke(instance, "reload", flags);
            if (state != null && state.getClass().getName().endsWith("ReloadState$Failure")) {
                Throwable cause = (Throwable) invoke(state, "throwable");
                throw new IllegalStateException("BetterHud reload failed", cause);
            }
        }

        @Override
        public void show(UUID playerId, String hudName) {
            Object player = hudPlayer(playerId);
            Object hud = hud(hudName);
            if (player == null || hud == null) {
                return;
            }
            invoke(hud, "add", player);
        }

        @Override
        public void update(UUID playerId) {
            Object player = hudPlayer(playerId);
            if (player != null) {
                invoke(player, "update");
            }
        }

        @Override
        public void hide(UUID playerId, String hudName) {
            Object player = hudPlayer(playerId);
            Object hud = hud(hudName);
            if (player != null && hud != null) {
                invoke(hud, "remove", player);
            }
        }

        private void registerPlaceholder(String containerMethod, String name, Function<UUID, ?> value) {
            Class<?> placeholderFunctionType = type(PLACEHOLDER_FUNCTION_CLASS);
            Object function = Proxy.newProxyInstance(
                    betterHudClassLoader,
                    new Class<?>[] {placeholderFunctionType},
                    (proxy, method, args) -> {
                        if (method.getName().equals("apply")) {
                            return (Function<Object, Object>) hudPlayer -> {
                                UUID playerId = (UUID) invoke(hudPlayer, "uuid");
                                return value.apply(playerId);
                            };
                        }
                        return objectMethod(proxy, method, args);
                    });
            Class<?> placeholderType = type(HUD_PLACEHOLDER_CLASS);
            Object placeholder;
            try {
                placeholder = placeholderType
                        .getMethod("of", placeholderFunctionType)
                        .invoke(null, function);
            } catch (ReflectiveOperationException error) {
                throw reflectionFailure("create BetterHud placeholder", error);
            }
            Object manager = invoke(instance(), "getPlaceholderManager");
            Object container = invoke(manager, containerMethod);
            invoke(container, "addPlaceholder", name, placeholder);
        }

        private Object hudPlayer(UUID playerId) {
            Object manager = invoke(instance(), "getPlayerManager");
            return invoke(manager, "getHudPlayer", playerId);
        }

        private Object hud(String hudName) {
            Object manager = invoke(instance(), "getHudManager");
            return invoke(manager, "getHud", hudName);
        }

        private Object instance() {
            return invokeStatic(type(BETTER_HUD_CLASS), "getInstance");
        }

        private Class<?> type(String name) {
            try {
                return Class.forName(name, true, betterHudClassLoader);
            } catch (ClassNotFoundException error) {
                throw new IllegalStateException("BetterHud API class is unavailable: " + name, error);
            }
        }

        private static Object invokeStatic(Class<?> type, String methodName, Object... arguments) {
            return invokeMethod(null, type, methodName, arguments);
        }

        private static Object invoke(Object target, String methodName, Object... arguments) {
            return invokeMethod(target, target.getClass(), methodName, arguments);
        }

        private static Object invokeMethod(
                Object target,
                Class<?> type,
                String methodName,
                Object... arguments) {
            Method method = findMethod(type, methodName, arguments);
            try {
                return method.invoke(target, arguments);
            } catch (IllegalAccessException | InvocationTargetException error) {
                throw reflectionFailure("invoke BetterHud method " + methodName, error);
            }
        }

        private static Method findMethod(Class<?> type, String name, Object[] arguments) {
            for (Method method : type.getMethods()) {
                if (!method.getName().equals(name) || method.getParameterCount() != arguments.length) {
                    continue;
                }
                Class<?>[] parameterTypes = method.getParameterTypes();
                boolean compatible = true;
                for (int index = 0; index < parameterTypes.length; index++) {
                    if (arguments[index] != null && !parameterTypes[index].isAssignableFrom(arguments[index].getClass())) {
                        compatible = false;
                        break;
                    }
                }
                if (compatible) {
                    return method;
                }
            }
            throw new IllegalStateException("BetterHud method is unavailable: " + type.getName() + "#" + name);
        }

        private static Object objectMethod(Object proxy, Method method, Object[] args) {
            return switch (method.getName()) {
                case "toString" -> "ImmortalMC BetterHud placeholder";
                case "hashCode" -> System.identityHashCode(proxy);
                case "equals" -> proxy == args[0];
                default -> throw new UnsupportedOperationException(method.getName());
            };
        }

        private static IllegalStateException reflectionFailure(String action, ReflectiveOperationException error) {
            Throwable cause = error instanceof InvocationTargetException invocation && invocation.getCause() != null
                    ? invocation.getCause()
                    : error;
            return new IllegalStateException("Unable to " + action, cause);
        }
    }
}
