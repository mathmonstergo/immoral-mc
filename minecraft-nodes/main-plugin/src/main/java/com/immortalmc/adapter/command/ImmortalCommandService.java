package com.immortalmc.adapter.command;

import java.util.Objects;
import java.util.function.Consumer;

public final class ImmortalCommandService {
    private final ImmortalCommandHandler commandHandler;
    private final HealthCommandRunner healthCommandRunner;
    private final HealthCommandMessages messages;

    public ImmortalCommandService(
            ImmortalCommandHandler commandHandler,
            HealthCommandRunner healthCommandRunner,
            HealthCommandMessages messages) {
        this.commandHandler = Objects.requireNonNull(commandHandler, "commandHandler");
        this.healthCommandRunner = Objects.requireNonNull(healthCommandRunner, "healthCommandRunner");
        this.messages = Objects.requireNonNull(messages, "messages");
    }

    public void execute(String[] args, Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");
        ImmortalCommandAction action = commandHandler.resolve(args);
        if (action == ImmortalCommandAction.HEALTH) {
            healthCommandRunner.run(sendMessage);
            return;
        }
        sendMessage.accept(messages.usage());
    }
}
