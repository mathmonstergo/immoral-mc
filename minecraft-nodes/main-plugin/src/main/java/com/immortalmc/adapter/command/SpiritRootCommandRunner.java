package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.logging.AdapterLogger;
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
    private final AdapterLogger logger;
    private final Consumer<Runnable> mainThreadDispatcher;

    public SpiritRootCommandRunner(
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

    public void run(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_test_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }

        PlayerLoginResult session = sessionCache.findByMinecraftUuid(source.minecraftUuid().orElseThrow())
                .orElse(null);
        if (session == null) {
            logger.warn("spirit_root_test_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=profile_missing");
            sendMessage.accept(messages.profileMissing());
            return;
        }

        sendMessage.accept(messages.detecting());
        logger.debug("spirit_root_test_start minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " account_id="
                + session.account().accountId());
        CompletableFuture<SpiritRootDetectionResult> detectionFuture;
        try {
            detectionFuture =
                    Objects.requireNonNull(detectSpiritRoot.apply(session.account().accountId()), "detectionFuture");
        } catch (RuntimeException error) {
            dispatchFailure(session, source.minecraftUuid().orElseThrow(), sendMessage, error);
            return;
        }

        detectionFuture.whenComplete((result, error) -> {
            if (error == null) {
                dispatchSuccess(session, source.minecraftUuid().orElseThrow(), sendMessage, result);
            } else {
                dispatchFailure(session, source.minecraftUuid().orElseThrow(), sendMessage, error);
            }
        });
    }

    private void dispatchSuccess(
            PlayerLoginResult session,
            UUID minecraftUuid,
            Consumer<String> sendMessage,
            SpiritRootDetectionResult result) {
        mainThreadDispatcher.accept(() -> {
            logger.info("spirit_root_test_success minecraft_uuid="
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
        });
    }

    private void dispatchFailure(
            PlayerLoginResult session, UUID minecraftUuid, Consumer<String> sendMessage, Throwable error) {
        Throwable cause = unwrap(error);
        mainThreadDispatcher.accept(() -> {
            logger.warn(
                    "spirit_root_test_failure minecraft_uuid="
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
