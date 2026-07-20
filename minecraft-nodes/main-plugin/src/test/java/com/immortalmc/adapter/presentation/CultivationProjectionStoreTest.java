package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.CultivationSnapshot;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class CultivationProjectionStoreTest {
    private static final UUID PLAYER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID LIFE_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID NEW_LIFE_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");

    @Test
    void confirmedMortalSnapshotIsDisplayedWithoutInventingLevelOne() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);

        assertTrue(store.confirm(
                PLAYER_ID,
                LIFE_ID,
                new CultivationSnapshot(
                        1, 0, "凡人", 0, 50, 0, 20, 50, 1, false, false, false)));

        CultivationProjectionStore.Projection projection = store.snapshot(PLAYER_ID);
        assertEquals("凡人", projection.realmName());
        assertEquals(50L, projection.maxExp());
        assertEquals(0.4, projection.reserveRatio());
    }

    @Test
    void missingStateIsDisplayDisabledRatherThanInventedGameplay() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);

        CultivationProjectionStore.Projection projection = store.snapshot(PLAYER_ID);

        assertFalse(projection.enabled());
        assertEquals("", projection.realmName());
        assertEquals(0L, projection.maxExp());
        assertEquals(0.0, projection.currentRatio());
    }

    @Test
    void storesOnlyLastConfirmedAuthoritativeRevision() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        assertTrue(store.confirm(PLAYER_ID, LIFE_ID, snapshot(7, "元婴后期", 0, 116_145_360L)));

        CultivationProjectionStore.Projection projection = store.snapshot(PLAYER_ID);

        assertTrue(projection.enabled());
        assertEquals("元婴后期", projection.realmName());
        assertEquals(0.0, projection.currentRatio());
        assertEquals(116_145_360L, projection.maxExp());
        assertEquals(0.5, projection.reserveRatio());

        assertFalse(store.confirm(PLAYER_ID, LIFE_ID, snapshot(6, "结丹后期", 50, 100)));
        assertEquals("元婴后期", store.snapshot(PLAYER_ID).realmName());
        assertEquals(7L, store.snapshot(PLAYER_ID).revision());
    }

    @Test
    void removeOnQuitDisablesProjection() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        store.confirm(PLAYER_ID, LIFE_ID, snapshot(1, "练气一层", 5, 10));

        store.remove(PLAYER_ID);

        assertFalse(store.snapshot(PLAYER_ID).enabled());
    }

    @Test
    void newLifeAcceptsLowRevisionAndRejectsLateOldLifeResponse() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        store.confirm(PLAYER_ID, LIFE_ID, snapshot(100, "元婴后期", 100, 100));

        store.beginLife(PLAYER_ID, NEW_LIFE_ID);

        assertFalse(store.snapshot(PLAYER_ID).enabled());
        assertFalse(store.confirm(PLAYER_ID, LIFE_ID, snapshot(101, "元婴后期", 100, 100)));
        assertTrue(store.confirm(PLAYER_ID, NEW_LIFE_ID, snapshot(1, "练气一层", 0, 10)));
        assertEquals("练气一层", store.snapshot(PLAYER_ID).realmName());
        assertEquals(1L, store.snapshot(PLAYER_ID).revision());
    }

    @Test
    void zeroReserveCapUsesDisplayOnlyEmptyOrFullRatio() {
        CultivationSnapshot empty = new CultivationSnapshot(
                1, 1, "练气一层", 0, 10, 0, 0, 0, 1, false, false, false);
        CultivationSnapshot preserved = new CultivationSnapshot(
                1, 1, "练气一层", 0, 10, 0, 5, 0, 2, false, true, false);

        assertEquals(0.0, empty.reserveRatio());
        assertEquals(1.0, preserved.reserveRatio());
    }

    private static CultivationSnapshot snapshot(long revision, String realm, long current, long maximum) {
        return new CultivationSnapshot(
                1,
                "元婴后期".equals(realm) ? 22 : 1,
                realm,
                current,
                maximum,
                current,
                maximum / 2,
                maximum,
                revision,
                current == maximum,
                false,
                false);
    }
}
