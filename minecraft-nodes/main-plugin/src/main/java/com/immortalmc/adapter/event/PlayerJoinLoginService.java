package com.immortalmc.adapter.event;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.BiFunction;
import java.util.function.Consumer;
import java.util.function.Predicate;

public final class PlayerJoinLoginService {
    private final BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer;
    private final PlayerSessionCache sessionCache;
    private final AdapterLogger logger;
    private final Consumer<Runnable> mainThreadDispatcher;
    private final Consumer<PlayerLoginResult> onSuccess;
    private final Predicate<UUID> playerIsOnline;
    private final AtomicLong joinSequence = new AtomicLong();
    private final ConcurrentMap<UUID, Long> currentJoins = new ConcurrentHashMap<>();

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher) {
        this(
                loginPlayer,
                sessionCache,
                logger,
                mainThreadDispatcher,
                ignored -> {},
                ignored -> true);
    }

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher,
            Consumer<PlayerLoginResult> onSuccess) {
        this(
                loginPlayer,
                sessionCache,
                logger,
                mainThreadDispatcher,
                onSuccess,
                ignored -> true);
    }

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher,
            Consumer<PlayerLoginResult> onSuccess,
            Predicate<UUID> playerIsOnline) {
        this.loginPlayer = Objects.requireNonNull(loginPlayer, "loginPlayer");
        this.sessionCache = Objects.requireNonNull(sessionCache, "sessionCache");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
        this.onSuccess = Objects.requireNonNull(onSuccess, "onSuccess");
        this.playerIsOnline = Objects.requireNonNull(playerIsOnline, "playerIsOnline");
    }

    public void loginOnJoin(UUID minecraftUuid, String playerName, Consumer<String> sendMessage) {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(playerName, "playerName");
        Objects.requireNonNull(sendMessage, "sendMessage");
        long join = joinSequence.incrementAndGet();
        currentJoins.put(minecraftUuid, join);
        logger.debug("player_login_start player_name=" + playerName + " minecraft_uuid=" + minecraftUuid);

        CompletableFuture<PlayerLoginResult> loginFuture;
        try {
            loginFuture = Objects.requireNonNull(loginPlayer.apply(minecraftUuid, playerName), "loginFuture");
        } catch (RuntimeException error) {
            dispatchFailure(minecraftUuid, playerName, join, error);
            return;
        }

        loginFuture.whenComplete((result, error) -> {
            if (!isCurrent(minecraftUuid, join)) {
                return;
            }
            if (error == null) {
                mainThreadDispatcher.accept(() -> {
                    if (!isCurrent(minecraftUuid, join) || !playerIsOnline.test(minecraftUuid)) {
                        currentJoins.remove(minecraftUuid, join);
                        return;
                    }
                    sessionCache.store(result);
                    onSuccess.accept(result);
                    logger.info("player_login_success player_name="
                            + result.account().playerName()
                            + " minecraft_uuid="
                            + result.account().minecraftUuid()
                            + " account_id="
                            + result.account().accountId()
                            + " life_id="
                            + result.currentLife().lifeId());
                });
            } else {
                dispatchFailure(minecraftUuid, playerName, join, error);
            }
        });
    }

    public void invalidate(UUID minecraftUuid) {
        currentJoins.remove(Objects.requireNonNull(minecraftUuid, "minecraftUuid"));
    }

    public void clear() {
        currentJoins.clear();
    }

    private void dispatchFailure(
            UUID minecraftUuid,
            String playerName,
            long join,
            Throwable error) {
        Throwable cause = unwrap(error);
        mainThreadDispatcher.accept(() -> {
            if (!isCurrent(minecraftUuid, join) || !playerIsOnline.test(minecraftUuid)) {
                currentJoins.remove(minecraftUuid, join);
                return;
            }
            currentJoins.remove(minecraftUuid, join);
            logger.warn(
                    "player_login_failure player_name="
                            + playerName
                            + " minecraft_uuid="
                            + minecraftUuid
                            + " reason="
                            + cause.getMessage(),
                    cause);
        });
    }

    private boolean isCurrent(UUID minecraftUuid, long join) {
        return Objects.equals(currentJoins.get(minecraftUuid), join);
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
