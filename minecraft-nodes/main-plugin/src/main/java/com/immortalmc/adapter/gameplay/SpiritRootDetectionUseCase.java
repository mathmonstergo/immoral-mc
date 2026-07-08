package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.function.Function;

public final class SpiritRootDetectionUseCase {
    private final Function<UUID, CompletableFuture<SpiritRootDetectionResult>> detectSpiritRoot;
    private final PlayerSessionCache sessionCache;
    private final SpiritRootCommandMessages messages;
    private final AdapterLogger logger;
    private final Consumer<Runnable> mainThreadDispatcher;

    public SpiritRootDetectionUseCase(
            Function<UUID, CompletableFuture<SpiritRootDetectionResult>> detectSpiritRoot,
            PlayerSessionCache sessionCache,
            SpiritRootCommandMessages messages,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher) {
        this.detectSpiritRoot = Objects.requireNonNull(detectSpiritRoot, "detectSpiritRoot");
        this.sessionCache = Objects.requireNonNull(sessionCache, "sessionCache");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
    }

    public void detectForPlayer(
            UUID minecraftUuid,
            String logEventPrefix,
            Consumer<String> sendMessage,
            Consumer<SpiritRootDetectionResult> onSuccess) {
        Objects.requireNonNull(minecraftUuid, "minecraftUuid");
        Objects.requireNonNull(logEventPrefix, "logEventPrefix");
        Objects.requireNonNull(sendMessage, "sendMessage");
        Objects.requireNonNull(onSuccess, "onSuccess");

        PlayerLoginResult session = sessionCache.findByMinecraftUuid(minecraftUuid).orElse(null);
        if (session == null) {
            logger.warn(logEventPrefix + "_rejected minecraft_uuid=" + minecraftUuid + " reason=profile_missing");
            sendMessage.accept(messages.profileMissing());
            return;
        }

        sendMessage.accept(messages.detecting());
        logger.debug(logEventPrefix + "_start minecraft_uuid="
                + minecraftUuid
                + " account_id="
                + session.account().accountId());
        CompletableFuture<SpiritRootDetectionResult> detectionFuture;
        try {
            detectionFuture =
                    Objects.requireNonNull(detectSpiritRoot.apply(session.account().accountId()), "detectionFuture");
        } catch (RuntimeException error) {
            dispatchFailure(logEventPrefix, session, minecraftUuid, sendMessage, error);
            return;
        }

        detectionFuture.whenComplete((result, error) -> {
            if (error == null) {
                dispatchSuccess(logEventPrefix, session, minecraftUuid, sendMessage, result, onSuccess);
            } else {
                dispatchFailure(logEventPrefix, session, minecraftUuid, sendMessage, error);
            }
        });
    }

    private void dispatchSuccess(
            String logEventPrefix,
            PlayerLoginResult session,
            UUID minecraftUuid,
            Consumer<String> sendMessage,
            SpiritRootDetectionResult result,
            Consumer<SpiritRootDetectionResult> onSuccess) {
        mainThreadDispatcher.accept(() -> {
            logger.info(logEventPrefix
                    + "_success minecraft_uuid="
                    + minecraftUuid
                    + " account_id="
                    + session.account().accountId()
                    + " life_id="
                    + result.lifeId()
                    + " quality="
                    + result.spiritRoot().quality()
                    + " elements="
                    + String.join(",", result.spiritRoot().elements())
                    + " already_detected="
                    + result.alreadyDetected());
            sendMessage.accept(messages.success(result));
            onSuccess.accept(result);
        });
    }

    private void dispatchFailure(
            String logEventPrefix,
            PlayerLoginResult session,
            UUID minecraftUuid,
            Consumer<String> sendMessage,
            Throwable error) {
        Throwable cause = unwrap(error);
        mainThreadDispatcher.accept(() -> {
            logger.warn(
                    logEventPrefix
                            + "_failure minecraft_uuid="
                            + minecraftUuid
                            + " account_id="
                            + session.account().accountId()
                            + " reason="
                            + cause.getMessage(),
                    cause);
            sendMessage.accept(messages.failure(error));
        });
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
