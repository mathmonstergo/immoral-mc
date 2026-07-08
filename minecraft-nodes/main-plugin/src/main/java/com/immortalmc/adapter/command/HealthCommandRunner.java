package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.function.Supplier;

public final class HealthCommandRunner {
    private final Supplier<CompletableFuture<HealthCheckResult>> healthCheck;
    private final HealthCommandMessages messages;
    private final AdapterLogger logger;
    private final Consumer<Runnable> mainThreadDispatcher;

    public HealthCommandRunner(
            Supplier<CompletableFuture<HealthCheckResult>> healthCheck,
            HealthCommandMessages messages,
            AdapterLogger logger,
            Consumer<Runnable> mainThreadDispatcher) {
        this.healthCheck = Objects.requireNonNull(healthCheck, "healthCheck");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
    }

    public void run(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage").accept(messages.checking());
        logger.debug("health_check_start");
        CompletableFuture<HealthCheckResult> healthCheckFuture;
        try {
            healthCheckFuture = Objects.requireNonNull(healthCheck.get(), "healthCheckFuture");
        } catch (RuntimeException error) {
            logger.warn("health_check_failure reason=" + unwrap(error).getMessage(), unwrap(error));
            dispatch(sendMessage, messages.failure(error));
            return;
        }

        healthCheckFuture.whenComplete((result, error) -> {
            if (error == null) {
                logger.info("health_check_success service="
                        + result.service()
                        + " status="
                        + result.status()
                        + " version="
                        + result.version());
                dispatch(sendMessage, messages.success(result));
            } else {
                logger.warn("health_check_failure reason=" + unwrap(error).getMessage(), unwrap(error));
                dispatch(sendMessage, messages.failure(error));
            }
        });
    }

    private void dispatch(Consumer<String> sendMessage, String message) {
        mainThreadDispatcher.accept(() -> sendMessage.accept(message));
    }

    private static Throwable unwrap(Throwable error) {
        if (error.getCause() == null) {
            return error;
        }
        return error.getCause();
    }
}
