package com.immortalmc.adapter.citizens;

import java.util.Optional;
import org.bukkit.command.CommandSender;

@FunctionalInterface
public interface CitizensNpcSelector {
    Optional<CitizensNpcSelection> selectedNpc(CommandSender sender);

    static CitizensNpcSelector unavailable() {
        return sender -> Optional.empty();
    }
}
