package com.immortalmc.adapter.command;

import java.util.Objects;
import java.util.function.Consumer;

public final class ImmortalCommandService {
    private final ImmortalCommandHandler commandHandler;
    private final HealthCommandRunner healthCommandRunner;
    private final SpiritRootCommandRunner spiritRootCommandRunner;
    private final HealthCommandMessages messages;

    public ImmortalCommandService(
            ImmortalCommandHandler commandHandler,
            HealthCommandRunner healthCommandRunner,
            HealthCommandMessages messages) {
        this(commandHandler, healthCommandRunner, null, messages);
    }

    public ImmortalCommandService(
            ImmortalCommandHandler commandHandler,
            HealthCommandRunner healthCommandRunner,
            SpiritRootCommandRunner spiritRootCommandRunner,
            HealthCommandMessages messages) {
        this.commandHandler = Objects.requireNonNull(commandHandler, "commandHandler");
        this.healthCommandRunner = Objects.requireNonNull(healthCommandRunner, "healthCommandRunner");
        this.spiritRootCommandRunner = spiritRootCommandRunner;
        this.messages = Objects.requireNonNull(messages, "messages");
    }

    public void execute(String[] args, Consumer<String> sendMessage) {
        execute(args, ImmortalCommandSource.console(), sendMessage);
    }

    public void execute(String[] args, ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");
        ImmortalCommandAction action = commandHandler.resolve(args);
        if (action == ImmortalCommandAction.HEALTH) {
            healthCommandRunner.run(sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.SPIRIT_ROOT && spiritRootCommandRunner != null) {
            spiritRootCommandRunner.run(source, sendMessage);
            return;
        }
        sendMessage.accept(messages.usage());
    }
}
