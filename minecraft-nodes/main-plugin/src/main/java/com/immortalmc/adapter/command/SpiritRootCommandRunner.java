package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionUseCase;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.function.Function;

public final class SpiritRootCommandRunner {
    private static final String LOG_EVENT_PREFIX = "spirit_root_test";

    private final SpiritRootDetectionUseCase detectionUseCase;
    private final AdapterLogger logger;
    private final SpiritRootCommandMessages messages;

    public SpiritRootCommandRunner(
            Function<UUID, CompletableFuture<SpiritRootDetectionResult>> detectSpiritRoot,
            PlayerSessionCache sessionCache,
            SpiritRootCommandMessages messages,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher) {
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.detectionUseCase = new SpiritRootDetectionUseCase(
                Objects.requireNonNull(detectSpiritRoot, "detectSpiritRoot"),
                Objects.requireNonNull(sessionCache, "sessionCache"),
                messages,
                logger,
                Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher"));
    }

    public SpiritRootCommandRunner(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootCommandMessages messages,
            AdapterLogger logger) {
        this.detectionUseCase = Objects.requireNonNull(detectionUseCase, "detectionUseCase");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void run(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_test_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }

        detectionUseCase.detectForPlayer(source.minecraftUuid().orElseThrow(), LOG_EVENT_PREFIX, sendMessage, result -> {});
    }
}
