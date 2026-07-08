package com.immortalmc.adapter.command;

import com.immortalmc.adapter.client.HealthCheckResult;
import java.util.Objects;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;
import java.util.function.Supplier;

public final class HealthCommandRunner {
    private final Supplier<CompletableFuture<HealthCheckResult>> healthCheck;
    private final HealthCommandMessages messages;
    private final Consumer<Runnable> mainThreadDispatcher;

    public HealthCommandRunner(
            Supplier<CompletableFuture<HealthCheckResult>> healthCheck,
            HealthCommandMessages messages,
            Consumer<Runnable> mainThreadDispatcher) {
        this.healthCheck = Objects.requireNonNull(healthCheck, "healthCheck");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.mainThreadDispatcher = Objects.requireNonNull(mainThreadDispatcher, "mainThreadDispatcher");
    }

    public void run(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage").accept(messages.checking());
        CompletableFuture<HealthCheckResult> healthCheckFuture;
        try {
            healthCheckFuture = Objects.requireNonNull(healthCheck.get(), "healthCheckFuture");
        } catch (RuntimeException error) {
            dispatch(sendMessage, messages.failure(error));
            return;
        }

        healthCheckFuture.whenComplete((result, error) -> {
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
