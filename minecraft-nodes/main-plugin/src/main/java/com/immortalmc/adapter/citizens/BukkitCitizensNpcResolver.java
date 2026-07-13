package com.immortalmc.adapter.citizens;

import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import net.citizensnpcs.api.CitizensAPI;
import net.citizensnpcs.api.npc.NPC;
import org.bukkit.entity.Entity;

public final class BukkitCitizensNpcResolver implements CitizensNpcResolver {
    @Override
    public Optional<UUID> persistentNpcUuid(Entity entity) {
        Objects.requireNonNull(entity, "entity");
        if (!CitizensAPI.hasImplementation()) {
            return Optional.empty();
        }
        NPC npc = CitizensAPI.getNPCRegistry().getNPC(entity);
        return npc == null ? Optional.empty() : Optional.of(npc.getUniqueId());
    }
}
