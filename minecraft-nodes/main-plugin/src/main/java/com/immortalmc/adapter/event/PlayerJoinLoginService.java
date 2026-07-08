package com.immortalmc.adapter.event;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.BiFunction;
import java.util.function.Consumer;

public final class PlayerJoinLoginService {
    private final BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer;
    private final PlayerSessionCache sessionCache;
    private final PlayerJoinMessages messages;
    private final Consumer<Runnable> mainThreadDispatcher;

    public PlayerJoinLoginService(
            BiFunction<UUID, String, CompletableFuture<PlayerLoginResult>> loginPlayer,
            PlayerSessionCache sessionCache,
            PlayerJoinMessages messages,
            Consumer<Runnable> mainThreadDispatcher) {
        this.loginPlayer = Objects.requireNonNull(loginPlayer, "loginPlayer");
        this.sessionCache = Objects.requireNonNull(sessionCache, "sessionCache");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
    }

    public void loginOnJoin(UUID minecraftUuid, String playerName, Consumer<String> sendMessage) {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(playerName, "playerName");
        Objects.requireNonNull(sendMessage, "sendMessage").accept(messages.loading());

        CompletableFuture<PlayerLoginResult> loginFuture;
        try {
            loginFuture = Objects.requireNonNull(loginPlayer.apply(minecraftUuid, playerName), "loginFuture");
        } catch (RuntimeException error) {
            dispatchFailure(sendMessage, error);
            return;
        }

        loginFuture.whenComplete((result, error) -> {
            if (error == null) {
                mainThreadDispatcher.accept(() -> {
                    sessionCache.store(result);
                    sendMessage.accept(messages.success());
                });
            } else {
                dispatchFailure(sendMessage, error);
            }
        });
    }

    private void dispatchFailure(Consumer<String> sendMessage, Throwable error) {
        mainThreadDispatcher.accept(() -> sendMessage.accept(messages.failure(error)));
    }
}
