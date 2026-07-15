package com.immortalmc.adapter.mythicmobs;

import com.immortalmc.adapter.combat.CombatSource;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Objects;
import java.util.UUID;
import java.util.regex.Pattern;

public record MythicMobDeathSnapshot(
        UUID eventId,
        String serverId,
        UUID entityUuid,
        String mobInternalName,
        BigDecimal mobLevel,
        CombatSource source,
        String worldKey,
        double x,
        double y,
        double z,
        Instant occurredAt) {
    private static final BigDecimal MAX_MOB_LEVEL = new BigDecimal("999999999.999");
    private static final Pattern STABLE_ID = Pattern.compile("[A-Za-z0-9_.:-]{1,128}");

    public MythicMobDeathSnapshot {
        Objects.requireNonNull(eventId, "eventId");
        Objects.requireNonNull(entityUuid, "entityUuid");
        Objects.requireNonNull(mobLevel, "mobLevel");
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(occurredAt, "occurredAt");
        requireStableId(serverId, 64, "serverId");
        requireStableId(mobInternalName, 128, "mobInternalName");
        if (mobLevel.signum() < 0
                || mobLevel.compareTo(MAX_MOB_LEVEL) > 0
                || mobLevel.scale() > 3) {
            throw new IllegalArgumentException("mobLevel is outside supported bounds");
        }
        if (worldKey == null || worldKey.isBlank() || worldKey.length() > 128) {
            throw new IllegalArgumentException("worldKey must be non-blank and at most 128 characters");
        }
        if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(z)) {
            throw new IllegalArgumentException("coordinates must be finite");
        }
    }

    public static UUID eventId(String serverId, UUID entityUuid) {
        requireStableId(serverId, 64, "serverId");
        Objects.requireNonNull(entityUuid, "entityUuid");
        return UUID.nameUUIDFromBytes(
                (serverId + ":mythicmob_death:" + entityUuid)
                        .getBytes(StandardCharsets.UTF_8));
    }

    private static void requireStableId(String value, int maxLength, String field) {
        if (value == null
                || value.length() > maxLength
                || !STABLE_ID.matcher(value).matches()) {
            throw new IllegalArgumentException(field + " has an invalid stable ID");
        }
    }
}
