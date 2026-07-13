package com.immortalmc.adapter.citizens;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;
import com.immortalmc.adapter.quest.QuestNpcPosition;
import com.immortalmc.adapter.quest.QuestNpcSource;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import net.citizensnpcs.api.CitizensAPI;
import net.citizensnpcs.api.npc.NPC;
import org.bukkit.Location;
import org.bukkit.entity.Entity;

public final class BukkitQuestNpcSource implements QuestNpcSource {
    private final EntityInteractionRegistry registry;

    public BukkitQuestNpcSource(EntityInteractionRegistry registry) {
        this.registry = Objects.requireNonNull(registry, "registry");
    }

    @Override
    public List<QuestNpcPosition> snapshot() {
        if (!CitizensAPI.hasImplementation()) {
            return List.of();
        }
        List<QuestNpcPosition> positions = new ArrayList<>();
        for (EntityInteractionDefinition definition : registry.listByAction(QuestProviderInteractionAction.ACTION)) {
            String providerId = definition.metadataValue(QuestProviderInteractionAction.PROVIDER_ID_KEY).orElse(null);
            UUID npcId = definition.metadataValue(QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY)
                    .map(BukkitQuestNpcSource::parseUuid)
                    .orElse(null);
            if (providerId == null || npcId == null) {
                continue;
            }
            NPC npc = CitizensAPI.getNPCRegistry().getByUniqueIdGlobal(npcId);
            if (npc == null || !npc.isSpawned()) {
                continue;
            }
            Entity entity = npc.getEntity();
            Location location = entity.getLocation();
            positions.add(new QuestNpcPosition(
                    npcId,
                    providerId,
                    entity.getWorld().getUID(),
                    location.getX(),
                    location.getY(),
                    location.getZ(),
                    location.getBlockX() >> 4,
                    location.getBlockZ() >> 4));
        }
        return List.copyOf(positions);
    }

    private static UUID parseUuid(String value) {
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ignored) {
            return null;
        }
    }
}
