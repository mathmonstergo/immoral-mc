package com.immortalmc.adapter.citizens;

import java.util.Objects;
import net.citizensnpcs.api.event.NPCRightClickEvent;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;

public final class CitizensNpcInteractionListener implements Listener {
    private final CitizensNpcInteractionHandler handler;

    public CitizensNpcInteractionListener(CitizensNpcInteractionHandler handler) {
        this.handler = Objects.requireNonNull(handler, "handler");
    }

    @EventHandler(ignoreCancelled = true)
    public void onNpcRightClick(NPCRightClickEvent event) {
        boolean handled = handler.handle(
                event.getNPC().getUniqueId(),
                event.getClicker(),
                event.getNPC().getEntity());
        if (handled) {
            event.setDelayedCancellation(true);
        }
    }
}
