package com.immortalmc.adapter.command;

import java.util.Locale;

public final class ImmortalCommandHandler {
    public ImmortalCommandAction resolve(String[] args) {
        if (args.length == 0) {
            return ImmortalCommandAction.USAGE;
        }
        if ("health".equals(args[0].toLowerCase(Locale.ROOT))) {
            return ImmortalCommandAction.HEALTH;
        }
        if ("spirit-root".equals(args[0].toLowerCase(Locale.ROOT))) {
            return ImmortalCommandAction.SPIRIT_ROOT;
        }
        if ("spirit-root-detector".equals(args[0].toLowerCase(Locale.ROOT))) {
            return resolveSpiritRootDetector(args);
        }
        if ("npc-dialogue".equals(args[0].toLowerCase(Locale.ROOT))) {
            return resolveNpcDialogue(args);
        }
        return ImmortalCommandAction.USAGE;
    }

    private ImmortalCommandAction resolveSpiritRootDetector(String[] args) {
        if (args.length < 2) {
            return ImmortalCommandAction.USAGE;
        }
        String action = args[1].toLowerCase(Locale.ROOT);
        if ("create".equals(action)) {
            return ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_CREATE;
        }
        if ("list".equals(action)) {
            return ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_LIST;
        }
        if ("remove".equals(action)) {
            return ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_REMOVE;
        }
        if ("set".equals(action)) {
            return ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_SET;
        }
        if ("reload".equals(action)) {
            return ImmortalCommandAction.SPIRIT_ROOT_DETECTOR_RELOAD;
        }
        return ImmortalCommandAction.USAGE;
    }

    private ImmortalCommandAction resolveNpcDialogue(String[] args) {
        if (args.length < 2) {
            return ImmortalCommandAction.USAGE;
        }
        String action = args[1].toLowerCase(Locale.ROOT);
        if ("set".equals(action) && args.length >= 3) {
            return ImmortalCommandAction.NPC_DIALOGUE_SET;
        }
        if ("list".equals(action)) {
            return ImmortalCommandAction.NPC_DIALOGUE_LIST;
        }
        if ("remove".equals(action)) {
            return ImmortalCommandAction.NPC_DIALOGUE_REMOVE;
        }
        if ("reload".equals(action)) {
            return ImmortalCommandAction.NPC_DIALOGUE_RELOAD;
        }
        return ImmortalCommandAction.USAGE;
    }
}
