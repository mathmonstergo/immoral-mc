package com.immortalmc.adapter.mythicmobs;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.combat.CombatAttributionKind;
import com.immortalmc.adapter.combat.CombatAttributionTracker;
import com.immortalmc.adapter.combat.CombatSource;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import io.lumine.mythic.api.mobs.MythicMob;
import io.lumine.mythic.bukkit.events.MythicMobDeathEvent;
import java.math.BigDecimal;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import org.bukkit.Location;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.junit.jupiter.api.Test;

class MythicMobDeathListenerTest {
    private static final UUID PLAYER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID LIFE_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID CAST_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final UUID ENTITY_ID =
            UUID.fromString("44444444-4444-4444-8444-444444444444");
    private static final Instant NOW = Instant.parse("2026-07-15T12:00:00Z");

    @Test
    void snapshotsTypedMythicFactsAndTrackedLethalSource() {
        Fixture fixture = fixtureWithAttribution("main-1");
        MythicMobDeathEvent event = event(12.5);

        fixture.listener().onDeath(event);

        MythicMobDeathSnapshot snapshot = fixture.snapshots().getFirst();
        assertEquals("main-1", snapshot.serverId());
        assertEquals(ENTITY_ID, snapshot.entityUuid());
        assertEquals("AzureWolf", snapshot.mobInternalName());
        assertEquals(new BigDecimal("12.5"), snapshot.mobLevel());
        assertEquals(PLAYER_ID, snapshot.source().playerUuid());
        assertEquals(LIFE_ID, snapshot.source().sourceLifeId());
        assertEquals("venom_mist", snapshot.source().techniqueId());
        assertEquals(CAST_ID, snapshot.source().castId());
        assertEquals(CombatAttributionKind.DAMAGE_OVER_TIME, snapshot.source().kind());
        assertEquals("minecraft:overworld", snapshot.worldKey());
        assertEquals(12.5, snapshot.x());
        assertEquals(64.0, snapshot.y());
        assertEquals(-8.25, snapshot.z());
        assertEquals(NOW, snapshot.occurredAt());
        verify(event, never()).getKiller();
    }

    @Test
    void deterministicEventIdUsesServerAndDeadEntityIdentity() {
        UUID first = MythicMobDeathSnapshot.eventId("main-1", ENTITY_ID);
        UUID replay = MythicMobDeathSnapshot.eventId("main-1", ENTITY_ID);
        UUID otherServer = MythicMobDeathSnapshot.eventId("main-2", ENTITY_ID);

        assertEquals(first, replay);
        assertTrue(!first.equals(otherServer));
    }

    @Test
    void missingTrackerAttributionProducesNoRewardSnapshot() {
        CombatAttributionTracker tracker =
                new CombatAttributionTracker(Duration.ofMinutes(15), 100);
        List<MythicMobDeathSnapshot> snapshots = new ArrayList<>();
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        MythicMobDeathListener listener = new MythicMobDeathListener(
                "main-1",
                tracker,
                snapshots::add,
                logger,
                Clock.fixed(NOW, ZoneOffset.UTC));

        listener.onDeath(event(12.5));

        assertTrue(snapshots.isEmpty());
        assertTrue(logger.messagesAt("warn").stream()
                .anyMatch(message -> message.contains("combat_kill_attribution_missing")));
    }

    @Test
    void invalidMythicLevelFailsInsteadOfBeingCoerced() {
        Fixture fixture = fixtureWithAttribution("main-1");

        assertThrows(IllegalArgumentException.class, () -> fixture.listener().onDeath(event(Double.NaN)));
        assertTrue(fixture.snapshots().isEmpty());
    }

    private static Fixture fixtureWithAttribution(String serverId) {
        CombatAttributionTracker tracker =
                new CombatAttributionTracker(Duration.ofMinutes(15), 100);
        tracker.recordDamage(
                ENTITY_ID,
                new CombatSource(
                        PLAYER_ID,
                        LIFE_ID,
                        "venom_mist",
                        CAST_ID,
                        CombatAttributionKind.DAMAGE_OVER_TIME,
                        NOW.minusSeconds(1),
                        NOW.plusSeconds(60)),
                10.0,
                true,
                NOW);
        List<MythicMobDeathSnapshot> snapshots = new ArrayList<>();
        MythicMobDeathListener listener = new MythicMobDeathListener(
                serverId,
                tracker,
                snapshots::add,
                new RecordingAdapterLogger(),
                Clock.fixed(NOW, ZoneOffset.UTC));
        return new Fixture(listener, snapshots);
    }

    private static MythicMobDeathEvent event(double level) {
        MythicMobDeathEvent event = mock(MythicMobDeathEvent.class);
        Entity entity = mock(Entity.class);
        World world = mock(World.class);
        Location location = mock(Location.class);
        MythicMob mob = mock(MythicMob.class);
        when(entity.getUniqueId()).thenReturn(ENTITY_ID);
        when(entity.getWorld()).thenReturn(world);
        when(entity.getLocation()).thenReturn(location);
        when(world.getKey()).thenReturn(NamespacedKey.minecraft("overworld"));
        when(location.getX()).thenReturn(12.5);
        when(location.getY()).thenReturn(64.0);
        when(location.getZ()).thenReturn(-8.25);
        when(mob.getInternalName()).thenReturn("AzureWolf");
        when(event.getEntity()).thenReturn(entity);
        when(event.getMobType()).thenReturn(mob);
        when(event.getMobLevel()).thenReturn(level);
        return event;
    }

    private record Fixture(
            MythicMobDeathListener listener,
            List<MythicMobDeathSnapshot> snapshots) {}
}
