package com.immortalmc.adapter.client;

import com.immortalmc.adapter.combat.CombatAttributionKind;
import com.immortalmc.adapter.combat.CombatSource;
import com.immortalmc.adapter.mythicmobs.MythicMobDeathSnapshot;
import java.util.Locale;
import java.util.Objects;
import java.util.UUID;

public record CombatKillEventRequest(
        int contractVersion,
        UUID eventId,
        String serverId,
        UUID entityUuid,
        String mobInternalName,
        String mobLevel,
        UUID killerUuid,
        UUID sourceLifeId,
        String attributionKind,
        String techniqueId,
        UUID castId,
        String world,
        double x,
        double y,
        double z,
        String occurredAt) {
    public CombatKillEventRequest {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported combat contract version");
        }
        Objects.requireNonNull(eventId, "eventId");
        Objects.requireNonNull(entityUuid, "entityUuid");
        Objects.requireNonNull(killerUuid, "killerUuid");
        requireText(serverId, "serverId");
        requireText(mobInternalName, "mobInternalName");
        requireText(mobLevel, "mobLevel");
        requireText(attributionKind, "attributionKind");
        requireText(world, "world");
        requireText(occurredAt, "occurredAt");
        if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(z)) {
            throw new IllegalArgumentException("Combat coordinates must be finite");
        }
    }

    public static CombatKillEventRequest fromSnapshot(MythicMobDeathSnapshot snapshot) {
        Objects.requireNonNull(snapshot, "snapshot");
        CombatSource source = snapshot.source();
        return new CombatKillEventRequest(
                1,
                snapshot.eventId(),
                snapshot.serverId(),
                snapshot.entityUuid(),
                snapshot.mobInternalName(),
                snapshot.mobLevel().toPlainString(),
                source.playerUuid(),
                source.sourceLifeId(),
                wireValue(source.kind()),
                source.techniqueId(),
                source.castId(),
                snapshot.worldKey(),
                snapshot.x(),
                snapshot.y(),
                snapshot.z(),
                snapshot.occurredAt().toString());
    }

    private static String wireValue(CombatAttributionKind kind) {
        return Objects.requireNonNull(kind, "kind").name().toLowerCase(Locale.ROOT);
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
    }
}
