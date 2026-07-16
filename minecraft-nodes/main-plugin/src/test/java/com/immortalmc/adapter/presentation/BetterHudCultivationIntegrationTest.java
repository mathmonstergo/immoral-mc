package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.CultivationSnapshot;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import org.junit.jupiter.api.Test;

class BetterHudCultivationIntegrationTest {
    private static final UUID PLAYER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID LIFE_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");

    @Test
    void registersAuthoritativePlaceholdersAndRefreshesConfirmedPlayer() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        store.confirm(PLAYER_ID, LIFE_ID, snapshot());
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        RecordingBridge bridge = new RecordingBridge();
        BetterHudCultivationIntegration integration =
                new BetterHudCultivationIntegration(store, logger, bridge);

        assertTrue(integration.start());
        integration.refresh(PLAYER_ID);

        assertTrue(bridge.resourcesInstalled);
        assertTrue(bridge.reloaded);
        assertEquals("元婴后期", bridge.strings.get("immortal_realm_name").apply(PLAYER_ID));
        assertEquals(0L, bridge.numbers.get("immortal_current").apply(PLAYER_ID).longValue());
        assertEquals(116_145_360L, bridge.numbers.get("immortal_max").apply(PLAYER_ID).longValue());
        assertEquals(0.0, bridge.numbers.get("immortal_current_ratio").apply(PLAYER_ID).doubleValue());
        assertEquals(58_072_680L, bridge.numbers.get("immortal_reserve").apply(PLAYER_ID).longValue());
        assertEquals(116_145_360L, bridge.numbers.get("immortal_reserve_cap").apply(PLAYER_ID).longValue());
        assertEquals(0.5, bridge.numbers.get("immortal_reserve_ratio").apply(PLAYER_ID).doubleValue());
        assertEquals(PLAYER_ID, bridge.shownPlayer);
        assertEquals("immortal_cultivation", bridge.shownHud);
        assertEquals(PLAYER_ID, bridge.updatedPlayer);
    }

    @Test
    void missingProjectionStaysHiddenAndMissingBetterHudFailsSafe() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        RecordingBridge bridge = new RecordingBridge();
        BetterHudCultivationIntegration integration = new BetterHudCultivationIntegration(
                store,
                new RecordingAdapterLogger(),
                bridge);
        assertTrue(integration.start());

        integration.refresh(PLAYER_ID);

        assertEquals(PLAYER_ID, bridge.hiddenPlayer);
        assertEquals(null, bridge.shownPlayer);

        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        BetterHudCultivationIntegration disabled =
                new BetterHudCultivationIntegration(store, logger, null);
        assertFalse(disabled.start());
        disabled.refresh(PLAYER_ID);
        assertTrue(logger.messagesAt("warn").stream()
                .anyMatch(message -> message.contains("betterhud_cultivation_unavailable")));
    }

    @Test
    void removeDetachesManagedHudWithoutChangingProjectionAuthority() {
        CultivationProjectionStore store = new CultivationProjectionStore();
        store.beginLife(PLAYER_ID, LIFE_ID);
        store.confirm(PLAYER_ID, LIFE_ID, snapshot());
        RecordingBridge bridge = new RecordingBridge();
        BetterHudCultivationIntegration integration = new BetterHudCultivationIntegration(
                store,
                new RecordingAdapterLogger(),
                bridge);
        integration.start();

        integration.remove(PLAYER_ID);

        assertEquals(PLAYER_ID, bridge.hiddenPlayer);
        assertTrue(store.snapshot(PLAYER_ID).enabled());
    }

    @Test
    void incompatibleOptionalBetterHudApiDisablesPresentationWithoutBreakingGameplay() {
        RecordingAdapterLogger logger = new RecordingAdapterLogger();
        RecordingBridge bridge = new RecordingBridge();
        bridge.startupFailure = new NoClassDefFoundError("Java 25 BetterHud API");
        BetterHudCultivationIntegration integration = new BetterHudCultivationIntegration(
                new CultivationProjectionStore(),
                logger,
                bridge);

        assertFalse(integration.start());

        assertTrue(logger.messagesAt("warn").stream()
                .anyMatch(message -> message.contains("betterhud_cultivation_start_failed")));
    }

    private static CultivationSnapshot snapshot() {
        return new CultivationSnapshot(
                1,
                22,
                "元婴后期",
                0,
                116_145_360L,
                900_000L,
                58_072_680L,
                116_145_360L,
                7,
                false,
                false,
                false);
    }

    private static final class RecordingBridge implements BetterHudCultivationIntegration.Bridge {
        private final Map<String, Function<UUID, String>> strings = new HashMap<>();
        private final Map<String, Function<UUID, Number>> numbers = new HashMap<>();
        private boolean resourcesInstalled;
        private boolean reloaded;
        private UUID shownPlayer;
        private String shownHud;
        private UUID updatedPlayer;
        private UUID hiddenPlayer;
        private LinkageError startupFailure;

        @Override
        public void installResources() {
            if (startupFailure != null) {
                throw startupFailure;
            }
            resourcesInstalled = true;
        }

        @Override
        public void registerString(String name, Function<UUID, String> value) {
            strings.put(name, value);
        }

        @Override
        public void registerNumber(String name, Function<UUID, Number> value) {
            numbers.put(name, value);
        }

        @Override
        public void reload() {
            reloaded = true;
        }

        @Override
        public void show(UUID playerId, String hudName) {
            shownPlayer = playerId;
            shownHud = hudName;
        }

        @Override
        public void update(UUID playerId) {
            updatedPlayer = playerId;
        }

        @Override
        public void hide(UUID playerId, String hudName) {
            hiddenPlayer = playerId;
        }
    }
}
