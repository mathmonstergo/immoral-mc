package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Optional;
import net.citizensnpcs.api.CitizensAPI;
import net.citizensnpcs.api.npc.NPC;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Entity;

public final class BukkitCitizensNpcSelector implements CitizensNpcSelector {
    @Override
    public Optional<CitizensNpcSelection> selectedNpc(CommandSender sender) {
        if (!CitizensAPI.hasImplementation()) {
            return Optional.empty();
        }
        NPC npc = CitizensAPI.getDefaultNPCSelector().getSelected(sender);
        if (npc == null) {
            return Optional.empty();
        }
        Entity entity = npc.getEntity();
        Optional<EntityInteractionEntity> spawnedEntity = entity == null
                ? Optional.empty()
                : Optional.of(new EntityInteractionEntity(
                        new EntityBinding(entity.getWorld().getName(), entity.getUniqueId()),
                        entity.getType().name()));
        return Optional.of(new CitizensNpcSelection(
                npc.getId(),
                npc.getName(),
                npc.getUniqueId(),
                spawnedEntity));
    }
}
