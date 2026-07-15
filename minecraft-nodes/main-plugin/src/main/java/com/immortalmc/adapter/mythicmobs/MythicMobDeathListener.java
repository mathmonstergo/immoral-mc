package com.immortalmc.adapter.mythicmobs;

import com.immortalmc.adapter.combat.CombatAttributionTracker;
import com.immortalmc.adapter.combat.LethalAttribution;
import com.immortalmc.adapter.logging.AdapterLogger;
import io.lumine.mythic.bukkit.events.MythicMobDeathEvent;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Consumer;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;

public final class MythicMobDeathListener implements Listener {
    private final String serverId;
    private final CombatAttributionTracker tracker;
    private final Consumer<MythicMobDeathSnapshot> snapshotSink;
    private final AdapterLogger logger;
    private final Clock clock;

    public MythicMobDeathListener(
            String serverId,
            CombatAttributionTracker tracker,
            Consumer<MythicMobDeathSnapshot> snapshotSink,
            AdapterLogger logger,
            Clock clock) {
        MythicMobDeathSnapshot.eventId(serverId, new UUID(0L, 0L));
        this.serverId = serverId;
        this.tracker = Objects.requireNonNull(tracker, "tracker");
        this.snapshotSink = Objects.requireNonNull(snapshotSink, "snapshotSink");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.clock = Objects.requireNonNull(clock, "clock");
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(MythicMobDeathEvent event) {
        Objects.requireNonNull(event, "event");
        Entity entity = Objects.requireNonNull(event.getEntity(), "event.entity");
        UUID entityUuid = entity.getUniqueId();
        Instant occurredAt = clock.instant();
        Optional<LethalAttribution> attribution = tracker.consumeLethal(entityUuid, occurredAt);
        if (attribution.isEmpty()) {
            logger.warn("combat_kill_attribution_missing entity_uuid=" + entityUuid);
            return;
        }

        Location location = entity.getLocation();
        MythicMobDeathSnapshot snapshot = new MythicMobDeathSnapshot(
                MythicMobDeathSnapshot.eventId(serverId, entityUuid),
                serverId,
                entityUuid,
                event.getMobType().getInternalName(),
                level(event.getMobLevel()),
                attribution.orElseThrow().source(),
                entity.getWorld().getKey().toString(),
                location.getX(),
                location.getY(),
                location.getZ(),
                occurredAt);
        snapshotSink.accept(snapshot);
    }

    private static BigDecimal level(double value) {
        if (!Double.isFinite(value)) {
            throw new IllegalArgumentException("Mythic mob level must be finite");
        }
        return BigDecimal.valueOf(value);
    }
}
