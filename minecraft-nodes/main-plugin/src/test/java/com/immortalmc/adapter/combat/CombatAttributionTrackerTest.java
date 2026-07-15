package com.immortalmc.adapter.combat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CombatAttributionTrackerTest {
    private static final UUID PLAYER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID LIFE_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID CAST_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final UUID TARGET_ID =
            UUID.fromString("44444444-4444-4444-8444-444444444444");
    private static final Instant START = Instant.parse("2026-07-15T12:00:00Z");

    @Test
    void recordsAndConsumesTheLethalPlayerOwnedSourceExactlyOnce() {
        CombatAttributionTracker tracker = tracker(10);
        CombatSource source = source(CombatAttributionKind.DAMAGE_OVER_TIME);

        tracker.recordDamage(TARGET_ID, source, 8.5, true, START.plusSeconds(5));

        LethalAttribution attribution =
                tracker.consumeLethal(TARGET_ID, START.plusSeconds(5)).orElseThrow();
        assertEquals(source, attribution.source());
        assertEquals(8.5, attribution.finalDamage());
        assertEquals(START.plusSeconds(5), attribution.occurredAt());
        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(5)).isEmpty());
    }

    @Test
    void nonlethalDamageNeverCreatesADeathAttribution() {
        CombatAttributionTracker tracker = tracker(10);

        tracker.recordDamage(
                TARGET_ID,
                source(CombatAttributionKind.DIRECT),
                2.0,
                false,
                START.plusSeconds(1));

        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(1)).isEmpty());
    }

    @Test
    void theLatestLethalSourceWinsForTheSameTarget() {
        CombatAttributionTracker tracker = tracker(10);
        tracker.recordDamage(
                TARGET_ID,
                source(CombatAttributionKind.DIRECT),
                4.0,
                true,
                START.plusSeconds(1));
        tracker.recordDamage(
                TARGET_ID,
                source(CombatAttributionKind.PROJECTILE),
                6.0,
                true,
                START.plusSeconds(2));

        LethalAttribution attribution =
                tracker.consumeLethal(TARGET_ID, START.plusSeconds(2)).orElseThrow();
        assertEquals(CombatAttributionKind.PROJECTILE, attribution.source().kind());
        assertEquals(6.0, attribution.finalDamage());
    }

    @Test
    void preservesEverySupportedAttributionKindAndSourceMetadata() {
        for (CombatAttributionKind kind : CombatAttributionKind.values()) {
            CombatAttributionTracker tracker = tracker(10);
            CombatSource source = source(kind);

            tracker.recordDamage(TARGET_ID, source, 4.0, true, START.plusSeconds(2));

            CombatSource stored = tracker
                    .consumeLethal(TARGET_ID, START.plusSeconds(2))
                    .orElseThrow()
                    .source();
            assertEquals(kind, stored.kind());
            assertEquals(PLAYER_ID, stored.playerUuid());
            assertEquals(LIFE_ID, stored.sourceLifeId());
            assertEquals("venom_mist", stored.techniqueId());
            assertEquals(CAST_ID, stored.castId());
        }
    }

    @Test
    void expiredOrOverAgeSourcesProduceNoAttribution() {
        CombatAttributionTracker tracker = new CombatAttributionTracker(Duration.ofSeconds(10), 10);
        CombatSource expired = new CombatSource(
                PLAYER_ID,
                LIFE_ID,
                "venom_mist",
                CAST_ID,
                CombatAttributionKind.DAMAGE_OVER_TIME,
                START,
                START.plusSeconds(5));
        CombatSource tooOld = new CombatSource(
                PLAYER_ID,
                LIFE_ID,
                "venom_mist",
                CAST_ID,
                CombatAttributionKind.DAMAGE_OVER_TIME,
                START,
                START.plusSeconds(60));

        tracker.recordDamage(TARGET_ID, expired, 4.0, true, START.plusSeconds(5));
        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(5)).isEmpty());

        tracker.recordDamage(TARGET_ID, tooOld, 4.0, true, START.plusSeconds(11));
        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(11)).isEmpty());
    }

    @Test
    void aStoredSourceCanExpireBeforeTheDeathEventConsumesIt() {
        CombatAttributionTracker tracker = tracker(10);
        CombatSource source = new CombatSource(
                PLAYER_ID,
                LIFE_ID,
                "venom_mist",
                CAST_ID,
                CombatAttributionKind.DAMAGE_OVER_TIME,
                START,
                START.plusSeconds(5));
        tracker.recordDamage(TARGET_ID, source, 4.0, true, START.plusSeconds(4));

        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(5)).isEmpty());
    }

    @Test
    void evictsTheOldestTargetWhenCapacityIsExceeded() {
        CombatAttributionTracker tracker = tracker(1);
        UUID newerTarget = UUID.fromString("55555555-5555-4555-8555-555555555555");

        tracker.recordDamage(TARGET_ID, source(CombatAttributionKind.DIRECT), 4.0, true, START);
        tracker.recordDamage(
                newerTarget,
                source(CombatAttributionKind.PROJECTILE),
                5.0,
                true,
                START.plusSeconds(1));

        assertTrue(tracker.consumeLethal(TARGET_ID, START.plusSeconds(1)).isEmpty());
        assertEquals(
                CombatAttributionKind.PROJECTILE,
                tracker.consumeLethal(newerTarget, START.plusSeconds(1))
                        .orElseThrow()
                        .source()
                        .kind());
    }

    @Test
    void clearAndClearAllRemoveDespawnedOrShutdownState() {
        CombatAttributionTracker tracker = tracker(10);
        UUID secondTarget = UUID.fromString("66666666-6666-4666-8666-666666666666");
        tracker.recordDamage(TARGET_ID, source(CombatAttributionKind.DIRECT), 4.0, true, START);
        tracker.recordDamage(secondTarget, source(CombatAttributionKind.DIRECT), 4.0, true, START);

        tracker.clear(TARGET_ID);

        assertTrue(tracker.consumeLethal(TARGET_ID, START).isEmpty());
        assertEquals(1, tracker.trackedTargetCount());

        tracker.clearAll();

        assertEquals(0, tracker.trackedTargetCount());
        assertTrue(tracker.consumeLethal(secondTarget, START).isEmpty());
    }

    @Test
    void rejectsInvalidSourceAndTrackerConfiguration() {
        assertThrows(
                IllegalArgumentException.class,
                () -> new CombatSource(
                        PLAYER_ID,
                        LIFE_ID,
                        "venom_mist",
                        CAST_ID,
                        CombatAttributionKind.DIRECT,
                        START,
                        START));
        assertThrows(
                IllegalArgumentException.class,
                () -> new CombatAttributionTracker(Duration.ZERO, 10));
        assertThrows(
                IllegalArgumentException.class,
                () -> new CombatAttributionTracker(Duration.ofSeconds(10), 0));
    }

    private static CombatAttributionTracker tracker(int maxTargets) {
        return new CombatAttributionTracker(Duration.ofMinutes(15), maxTargets);
    }

    private static CombatSource source(CombatAttributionKind kind) {
        return new CombatSource(
                PLAYER_ID,
                LIFE_ID,
                "venom_mist",
                CAST_ID,
                kind,
                START,
                START.plusSeconds(60));
    }
}
