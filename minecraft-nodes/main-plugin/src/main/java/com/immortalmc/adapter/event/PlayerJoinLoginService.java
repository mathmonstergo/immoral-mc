package com.immortalmc.adapter.event;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.BiFunction;
import java.util.function.Consumer;

public final class PlayerJoinLoginService {
    private final BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer;
    private final PlayerSessionCache sessionCache;
    private final AdapterLogger logger;
    private final Consumer<Runnable> mainThreadDispatcher;
    private final Consumer<PlayerLoginResult> onSuccess;

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher) {
        this(loginPlayer, sessionCache, logger, mainThreadDispatcher, ignored -> {});
    }

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher,
            Consumer<PlayerLoginResult> onSuccess) {
        this.loginPlayer = Objects.requireNonNull(loginPlayer, "loginPlayer");
        this.sessionCache = Objects.requireNonNull(sessionCache, "sessionCache");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
        this.onSuccess = Objects.requireNonNull(onSuccess, "onSuccess");
    }

    public void loginOnJoin(UUID minecraftUuid, String playerName, Consumer<String> sendMessage) {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(playerName, "playerName");
        Objects.requireNonNull(sendMessage, "sendMessage");
        logger.debug("player_login_start player_name=" + playerName + " minecraft_uuid=" + minecraftUuid);

        CompletableFuture<PlayerLoginResult> loginFuture;
        try {
            loginFuture = Objects.requireNonNull(loginPlayer.apply(minecraftUuid, playerName), "loginFuture");
        } catch (RuntimeException error) {
            dispatchFailure(minecraftUuid, playerName, error);
            return;
        }

        loginFuture.whenComplete((result, error) -> {
            if (error == null) {
                mainThreadDispatcher.accept(() -> {
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
                dispatchFailure(minecraftUuid, playerName, error);
            }
        });
    }

    private void dispatchFailure(UUID minecraftUuid, String playerName, Throwable error) {
        Throwable cause = unwrap(error);
        mainThreadDispatcher.accept(() -> logger.warn(
                "player_login_failure player_name="
                        + playerName
                        + " minecraft_uuid="
                        + minecraftUuid
                        + " reason="
                        + cause.getMessage(),
                cause));
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
