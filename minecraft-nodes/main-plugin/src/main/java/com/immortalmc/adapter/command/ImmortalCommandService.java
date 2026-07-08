package com.immortalmc.adapter.command;

import java.util.Objects;
import java.util.function.Consumer;

public final class ImmortalCommandService {
    private final ImmortalCommandHandler commandHandler;
    private final HealthCommandRunner healthCommandRunner;
    private final SpiritRootCommandRunner spiritRootCommandRunner;
    private final SpiritRootDetectorAdminRunner spiritRootDetectorAdminRunner;
    private final NpcDialogueAdminRunner npcDialogueAdminRunner;
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
        this(commandHandler, healthCommandRunner, spiritRootCommandRunner, null, messages);
    }

    public ImmortalCommandService(
            ImmortalCommandHandler commandHandler,
            HealthCommandRunner healthCommandRunner,
            SpiritRootCommandRunner spiritRootCommandRunner,
            SpiritRootDetectorAdminRunner spiritRootDetectorAdminRunner,
            HealthCommandMessages messages) {
        this(commandHandler, healthCommandRunner, spiritRootCommandRunner, spiritRootDetectorAdminRunner, null, messages);
    }

    public ImmortalCommandService(
            ImmortalCommandHandler commandHandler,
            HealthCommandRunner healthCommandRunner,
            SpiritRootCommandRunner spiritRootCommandRunner,
            SpiritRootDetectorAdminRunner spiritRootDetectorAdminRunner,
            NpcDialogueAdminRunner npcDialogueAdminRunner,
            HealthCommandMessages messages) {
        this.commandHandler = Objects.requireNonNull(commandHandler, "commandHandler");
        this.healthCommandRunner = Objects.requireNonNull(healthCommandRunner, "healthCommandRunner");
        this.spiritRootCommandRunner = spiritRootCommandRunner;
        this.spiritRootDetectorAdminRunner = spiritRootDetectorAdminRunner;
        this.npcDialogueAdminRunner = npcDialogueAdminRunner;
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
        if (action == ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_CREATE && spiritRootDetectorAdminRunner != null) {
            spiritRootDetectorAdminRunner.createDetector(source, sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_LIST && spiritRootDetectorAdminRunner != null) {
            spiritRootDetectorAdminRunner.listDetectors(sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_REMOVE && spiritRootDetectorAdminRunner != null) {
            spiritRootDetectorAdminRunner.removeLookedAtDetector(source, sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_SET && spiritRootDetectorAdminRunner != null) {
            spiritRootDetectorAdminRunner.setLookedAtEntityAsDetector(source, sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_RELOAD && spiritRootDetectorAdminRunner != null) {
            spiritRootDetectorAdminRunner.reload(sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.NPC_DIALOGUE_SET && npcDialogueAdminRunner != null) {
            npcDialogueAdminRunner.setLookedAtEntityAsDialogue(source, args[2], sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.NPC_DIALOGUE_LIST && npcDialogueAdminRunner != null) {
            npcDialogueAdminRunner.listDialogues(sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.NPC_DIALOGUE_REMOVE && npcDialogueAdminRunner != null) {
            npcDialogueAdminRunner.removeLookedAtDialogue(source, sendMessage);
            return;
        }
        if (action == ImmortalCommandAction.NPC_DIALOGUE_RELOAD && npcDialogueAdminRunner != null) {
            npcDialogueAdminRunner.reload(sendMessage);
            return;
        }
        sendMessage.accept(messages.usage());
    }
}
