package com.immortalmc.adapter.outbox;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.combat.CombatAttributionKind;
import com.immortalmc.adapter.combat.CombatSource;
import com.immortalmc.adapter.mythicmobs.MythicMobDeathSnapshot;
import java.math.BigDecimal;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SqliteKillOutboxTest {
    private static final Instant NOW = Instant.parse("2026-07-15T12:00:00Z");
    private static final UUID EVENT_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");

    @TempDir
    Path tempDir;

    @Test
    void initializesWalFullForeignKeysAndBusyTimeout() throws Exception {
        try (SqliteKillOutbox outbox = outbox()) {
            SqlitePragmas pragmas = outbox.readPragmas().get(2, TimeUnit.SECONDS);

            assertEquals("wal", pragmas.journalMode());
            assertEquals(2, pragmas.synchronous());
            assertTrue(pragmas.foreignKeys());
            assertEquals(5000, pragmas.busyTimeoutMs());
        }
    }

    @Test
    void committedAppendIsIdempotentAndSurvivesRestart() throws Exception {
        Path database = database();
        try (SqliteKillOutbox outbox = outbox(database)) {
            assertTrue(outbox.append(request()).get(2, TimeUnit.SECONDS));
            assertFalse(outbox.append(request()).get(2, TimeUnit.SECONDS));
            assertEquals(1, outbox.pendingCount().get(2, TimeUnit.SECONDS));
        }

        try (SqliteKillOutbox reopened = outbox(database)) {
            assertEquals(1, reopened.pendingCount().get(2, TimeUnit.SECONDS));
            assertEquals(
                    EVENT_ID,
                    reopened.claimDue(10, NOW, Duration.ofSeconds(30))
                            .get(2, TimeUnit.SECONDS)
                            .getFirst()
                            .request()
                            .eventId());
        }
    }

    @Test
    void expiredLeaseIsRecoveredAndClaimedAgain() throws Exception {
        try (SqliteKillOutbox outbox = outbox()) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);
            KillOutboxRow first = outbox.claimDue(10, NOW, Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .getFirst();
            assertEquals(1, first.attemptCount());
            assertEquals(KillOutboxStatus.IN_FLIGHT, first.status());

            assertTrue(outbox.claimDue(10, NOW.plusSeconds(4), Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .isEmpty());
            KillOutboxRow recovered = outbox.claimDue(
                            10,
                            NOW.plusSeconds(5),
                            Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .getFirst();
            assertEquals(2, recovered.attemptCount());
        }
    }

    @Test
    void acknowledgementRetryAndDeadLetterUseExplicitStateTransitions() throws Exception {
        try (SqliteKillOutbox outbox = outbox(tempDir.resolve("ack.sqlite3"))) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);
            outbox.claimDue(1, NOW, Duration.ofSeconds(5)).get(2, TimeUnit.SECONDS);
            outbox.retry(EVENT_ID, NOW.plusSeconds(10), "service unavailable")
                    .get(2, TimeUnit.SECONDS);
            assertTrue(outbox.claimDue(1, NOW.plusSeconds(9), Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .isEmpty());
            outbox.claimDue(1, NOW.plusSeconds(10), Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS);
            outbox.deadLetter(EVENT_ID, "invalid local payload").get(2, TimeUnit.SECONDS);
            assertEquals(1, outbox.deadLetterCount().get(2, TimeUnit.SECONDS));
            assertEquals(0, outbox.pendingCount().get(2, TimeUnit.SECONDS));
        }

        try (SqliteKillOutbox outbox = outbox()) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);
            outbox.claimDue(1, NOW, Duration.ofSeconds(5)).get(2, TimeUnit.SECONDS);
            outbox.acknowledge(List.of(EVENT_ID)).get(2, TimeUnit.SECONDS);
            assertEquals(0, outbox.totalCount().get(2, TimeUnit.SECONDS));
        }
    }

    @Test
    void malformedPayloadIsDeadLetteredDuringClaim() throws Exception {
        Path database = tempDir.resolve("malformed.sqlite3");
        try (SqliteKillOutbox outbox = outbox(database)) {
            outbox.append(request()).get(2, TimeUnit.SECONDS);
            try (Connection connection = DriverManager.getConnection("jdbc:sqlite:" + database);
                    Statement statement = connection.createStatement()) {
                statement.executeUpdate(
                        "UPDATE kill_outbox SET payload_json = '{not-json' WHERE event_id = '"
                                + EVENT_ID
                                + "'");
            }

            assertTrue(outbox.claimDue(1, NOW, Duration.ofSeconds(5))
                    .get(2, TimeUnit.SECONDS)
                    .isEmpty());
            assertEquals(1, outbox.deadLetterCount().get(2, TimeUnit.SECONDS));
        }
    }

    private SqliteKillOutbox outbox() {
        return outbox(database());
    }

    private SqliteKillOutbox outbox(Path database) {
        return new SqliteKillOutbox(
                database,
                Duration.ofSeconds(5),
                64,
                Clock.fixed(NOW, ZoneOffset.UTC),
                new ObjectMapper());
    }

    private Path database() {
        return tempDir.resolve("combat-outbox.sqlite3");
    }

    private static CombatKillEventRequest request() {
        UUID entityId = UUID.fromString("22222222-2222-4222-8222-222222222222");
        UUID playerId = UUID.fromString("33333333-3333-4333-8333-333333333333");
        UUID lifeId = UUID.fromString("44444444-4444-4444-8444-444444444444");
        MythicMobDeathSnapshot snapshot = new MythicMobDeathSnapshot(
                EVENT_ID,
                "main-1",
                entityId,
                "AzureWolf",
                new BigDecimal("12.5"),
                new CombatSource(
                        playerId,
                        lifeId,
                        "venom_mist",
                        UUID.fromString("55555555-5555-4555-8555-555555555555"),
                        CombatAttributionKind.DAMAGE_OVER_TIME,
                        NOW.minusSeconds(1),
                        NOW.plusSeconds(60)),
                "minecraft:overworld",
                12.5,
                64.0,
                -8.25,
                NOW);
        return CombatKillEventRequest.fromSnapshot(snapshot);
    }
}
