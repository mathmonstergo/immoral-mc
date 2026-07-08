package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.function.Function;

public final class SpiritRootCommandRunner {
    private final Function<UUID, CompletableFuture<SpiritRootDetectionResult>> detectSpiritRoot;
    private final PlayerSessionCache sessionCache;
    private final SpiritRootCommandMessages messages;
    private final Consumer<Runnable> mainThreadDispatcher;

    public SpiritRootCommandRunner(
            Function<UUID, CompletableFuture<SpiritRootDetectionResult>> detectSpiritRoot,
            PlayerSessionCache sessionCache,
            SpiritRootCommandMessages messages,
            Consumer<Runnable> mainThreadDispatcher) {
        this.detectSpiritRoot = Objects.requireNonNull(detectSpiritRoot, "detectSpiritRoot");
        this.sessionCache = Objects.requireNonNull(sessionCache, "sessionCache");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
    }

    public void run(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            sendMessage.accept(messages.playerOnly());
            return;
        }

        PlayerLoginResult session = sessionCache.findByMinecraftUuid(source.minecraftUuid().orElseThrow())
                .orElse(null);
        if (session == null) {
            sendMessage.accept(messages.profileMissing());
            return;
        }

        sendMessage.accept(messages.detecting());
        CompletableFuture<SpiritRootDetectionResult> detectionFuture;
        try {
            detectionFuture =
                    Objects.requireNonNull(detectSpiritRoot.apply(session.account().accountId()), "detectionFuture");
        } catch (RuntimeException error) {
            dispatch(sendMessage, messages.failure(error));
            return;
        }

        detectionFuture.whenComplete((result, error) -> {
            if (error == null) {
                dispatch(sendMessage, messages.success(result));
            } else {
                dispatch(sendMessage, messages.failure(error));
            }
        });
    }

    private void dispatch(Consumer<String> sendMessage, String message) {
        mainThreadDispatcher.accept(() -> sendMessage.accept(message));
    }
}
