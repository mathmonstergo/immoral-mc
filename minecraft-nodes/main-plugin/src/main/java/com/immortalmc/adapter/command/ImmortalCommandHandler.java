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
        return ImmortalCommandAction.USAGE;
    }
}
