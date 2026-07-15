package com.immortalmc.adapter.outbox;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.Optional;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class SqliteKillOutbox implements AutoCloseable {
    private final Path databasePath;
    private final int busyTimeoutMs;
    private final Clock clock;
    private final ObjectMapper objectMapper;
    private final ThreadPoolExecutor writer;
    private final AtomicBoolean closed = new AtomicBoolean();
    private Connection connection;

    public SqliteKillOutbox(
            Path databasePath,
            Duration busyTimeout,
            int writerQueueCapacity,
            Clock clock,
            ObjectMapper objectMapper) {
        this.databasePath = Objects.requireNonNull(databasePath, "databasePath").toAbsolutePath();
        Objects.requireNonNull(busyTimeout, "busyTimeout");
        if (busyTimeout.isNegative()
                || busyTimeout.isZero()
                || busyTimeout.toMillis() > Integer.MAX_VALUE) {
            throw new IllegalArgumentException("busyTimeout is outside supported bounds");
        }
        if (writerQueueCapacity <= 0) {
            throw new IllegalArgumentException("writerQueueCapacity must be positive");
        }
        this.busyTimeoutMs = Math.toIntExact(busyTimeout.toMillis());
        this.clock = Objects.requireNonNull(clock, "clock");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper")
                .copy()
                .setPropertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE);
        this.writer = new ThreadPoolExecutor(
                1,
                1,
                0L,
                TimeUnit.MILLISECONDS,
                new ArrayBlockingQueue<>(writerQueueCapacity),
                runnable -> {
                    Thread thread = new Thread(runnable, "immortalmc-combat-outbox-writer");
                    thread.setDaemon(true);
                    return thread;
                },
                new ThreadPoolExecutor.AbortPolicy());
        this.connection = submitInternal(this::openAndInitialize).join();
    }

    public CompletableFuture<Boolean> append(CombatKillEventRequest request) {
        Objects.requireNonNull(request, "request");
        return submit(() -> appendNow(request));
    }

    public CompletableFuture<List<KillOutboxRow>> claimDue(
            int limit,
            Instant now,
            Duration leaseDuration) {
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        Objects.requireNonNull(now, "now");
        Objects.requireNonNull(leaseDuration, "leaseDuration");
        if (leaseDuration.isNegative() || leaseDuration.isZero()) {
            throw new IllegalArgumentException("leaseDuration must be positive");
        }
        return submit(() -> claimDueNow(limit, now, leaseDuration));
    }

    public CompletableFuture<Void> acknowledge(List<UUID> eventIds) {
        List<UUID> ids = List.copyOf(Objects.requireNonNull(eventIds, "eventIds"));
        return submit(() -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    "DELETE FROM kill_outbox WHERE event_id = ?")) {
                for (UUID eventId : ids) {
                    statement.setString(1, eventId.toString());
                    statement.addBatch();
                }
                statement.executeBatch();
            }
            return null;
        });
    }

    public CompletableFuture<Void> retry(UUID eventId, Instant nextAttemptAt, String error) {
        Objects.requireNonNull(eventId, "eventId");
        Objects.requireNonNull(nextAttemptAt, "nextAttemptAt");
        return submit(() -> {
            try (PreparedStatement statement = connection.prepareStatement(
                    """
                    UPDATE kill_outbox
                    SET delivery_status = 'pending', next_attempt_at_ms = ?,
                        lease_until_ms = NULL, last_error = ?, updated_at_ms = ?
                    WHERE event_id = ? AND delivery_status = 'in_flight'
                    """)) {
                statement.setLong(1, nextAttemptAt.toEpochMilli());
                statement.setString(2, error);
                statement.setLong(3, clock.instant().toEpochMilli());
                statement.setString(4, eventId.toString());
                statement.executeUpdate();
            }
            return null;
        });
    }

    public CompletableFuture<Void> deadLetter(UUID eventId, String error) {
        Objects.requireNonNull(eventId, "eventId");
        return submit(() -> {
            markDeadLetter(eventId.toString(), error, clock.instant().toEpochMilli());
            return null;
        });
    }

    public CompletableFuture<Integer> pendingCount() {
        return count("delivery_status <> 'dead_letter'");
    }

    public CompletableFuture<Integer> deadLetterCount() {
        return count("delivery_status = 'dead_letter'");
    }

    public CompletableFuture<Integer> totalCount() {
        return count("1 = 1");
    }

    public CompletableFuture<Optional<Duration>> oldestPendingAge(Instant now) {
        Objects.requireNonNull(now, "now");
        return submit(() -> {
            try (Statement statement = connection.createStatement();
                    ResultSet result = statement.executeQuery(
                            "SELECT MIN(created_at_ms) FROM kill_outbox WHERE delivery_status <> 'dead_letter'")) {
                long oldest = result.getLong(1);
                if (result.wasNull()) {
                    return Optional.empty();
                }
                return Optional.of(Duration.ofMillis(Math.max(0L, now.toEpochMilli() - oldest)));
            }
        });
    }

    public CompletableFuture<Void> checkpoint() {
        return submit(() -> {
            checkpointNow();
            return null;
        });
    }

    CompletableFuture<SqlitePragmas> readPragmas() {
        return submit(() -> new SqlitePragmas(
                pragmaString("journal_mode"),
                pragmaInt("synchronous"),
                pragmaInt("foreign_keys") == 1,
                pragmaInt("busy_timeout")));
    }

    @Override
    public void close() {
        if (!closed.compareAndSet(false, true)) {
            return;
        }
        submitInternal(() -> {
                    checkpointNow();
                    connection.close();
                    return null;
                })
                .join();
        writer.shutdown();
        try {
            if (!writer.awaitTermination(5, TimeUnit.SECONDS)) {
                throw new IllegalStateException("SQLite outbox writer did not stop");
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while stopping SQLite outbox", error);
        }
    }

    private Connection openAndInitialize() throws SQLException, IOException, ClassNotFoundException {
        Path parent = databasePath.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        Class.forName("org.sqlite.JDBC");
        Connection opened = DriverManager.getConnection("jdbc:sqlite:" + databasePath);
        try (Statement statement = opened.createStatement()) {
            statement.execute("PRAGMA journal_mode = WAL");
            statement.execute("PRAGMA synchronous = FULL");
            statement.execute("PRAGMA foreign_keys = ON");
            statement.execute("PRAGMA busy_timeout = " + busyTimeoutMs);
            statement.execute("""
                    CREATE TABLE IF NOT EXISTS kill_outbox (
                        event_id TEXT PRIMARY KEY,
                        server_id TEXT NOT NULL,
                        entity_uuid TEXT NOT NULL,
                        mob_internal_name TEXT NOT NULL,
                        killer_uuid TEXT NOT NULL,
                        world_key TEXT NOT NULL,
                        occurred_at_ms INTEGER NOT NULL,
                        payload_json TEXT NOT NULL,
                        delivery_status TEXT NOT NULL DEFAULT 'pending',
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        next_attempt_at_ms INTEGER NOT NULL,
                        lease_until_ms INTEGER,
                        last_error TEXT,
                        created_at_ms INTEGER NOT NULL,
                        updated_at_ms INTEGER NOT NULL,
                        CHECK (delivery_status IN ('pending', 'in_flight', 'dead_letter')),
                        CHECK (attempt_count >= 0)
                    )
                    """);
            statement.execute("""
                    CREATE INDEX IF NOT EXISTS ix_kill_outbox_due
                    ON kill_outbox (delivery_status, next_attempt_at_ms)
                    """);
        } catch (SQLException error) {
            opened.close();
            throw error;
        }
        return opened;
    }

    private boolean appendNow(CombatKillEventRequest request) throws SQLException, IOException {
        long now = clock.instant().toEpochMilli();
        try (PreparedStatement statement = connection.prepareStatement(
                """
                INSERT OR IGNORE INTO kill_outbox (
                    event_id, server_id, entity_uuid, mob_internal_name, killer_uuid,
                    world_key, occurred_at_ms, payload_json, delivery_status,
                    attempt_count, next_attempt_at_ms, created_at_ms, updated_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?, ?)
                """)) {
            statement.setString(1, request.eventId().toString());
            statement.setString(2, request.serverId());
            statement.setString(3, request.entityUuid().toString());
            statement.setString(4, request.mobInternalName());
            statement.setString(5, request.killerUuid().toString());
            statement.setString(6, request.world());
            statement.setLong(7, Instant.parse(request.occurredAt()).toEpochMilli());
            statement.setString(8, objectMapper.writeValueAsString(request));
            statement.setLong(9, now);
            statement.setLong(10, now);
            statement.setLong(11, now);
            return statement.executeUpdate() == 1;
        }
    }

    private List<KillOutboxRow> claimDueNow(int limit, Instant now, Duration leaseDuration)
            throws SQLException {
        long nowMs = now.toEpochMilli();
        long leaseUntilMs = now.plus(leaseDuration).toEpochMilli();
        boolean originalAutoCommit = connection.getAutoCommit();
        connection.setAutoCommit(false);
        try {
            try (PreparedStatement recover = connection.prepareStatement(
                    """
                    UPDATE kill_outbox
                    SET delivery_status = 'pending', lease_until_ms = NULL,
                        next_attempt_at_ms = ?, updated_at_ms = ?
                    WHERE delivery_status = 'in_flight' AND lease_until_ms <= ?
                    """)) {
                recover.setLong(1, nowMs);
                recover.setLong(2, nowMs);
                recover.setLong(3, nowMs);
                recover.executeUpdate();
            }

            List<RawRow> candidates = new ArrayList<>();
            try (PreparedStatement select = connection.prepareStatement(
                    """
                    SELECT event_id, payload_json, attempt_count, next_attempt_at_ms, last_error
                    FROM kill_outbox
                    WHERE delivery_status = 'pending' AND next_attempt_at_ms <= ?
                    ORDER BY next_attempt_at_ms, created_at_ms
                    LIMIT ?
                    """)) {
                select.setLong(1, nowMs);
                select.setInt(2, limit);
                try (ResultSet rows = select.executeQuery()) {
                    while (rows.next()) {
                        candidates.add(new RawRow(
                                rows.getString("event_id"),
                                rows.getString("payload_json"),
                                rows.getInt("attempt_count"),
                                rows.getLong("next_attempt_at_ms"),
                                rows.getString("last_error")));
                    }
                }
            }

            List<KillOutboxRow> claimed = new ArrayList<>();
            for (RawRow candidate : candidates) {
                CombatKillEventRequest request;
                try {
                    request = objectMapper.readValue(
                            candidate.payloadJson(),
                            CombatKillEventRequest.class);
                } catch (IOException | RuntimeException error) {
                    markDeadLetter(
                            candidate.eventId(),
                            "malformed payload: " + error.getMessage(),
                            nowMs);
                    continue;
                }
                try (PreparedStatement update = connection.prepareStatement(
                        """
                        UPDATE kill_outbox
                        SET delivery_status = 'in_flight', attempt_count = attempt_count + 1,
                            lease_until_ms = ?, updated_at_ms = ?
                        WHERE event_id = ? AND delivery_status = 'pending'
                        """)) {
                    update.setLong(1, leaseUntilMs);
                    update.setLong(2, nowMs);
                    update.setString(3, candidate.eventId());
                    if (update.executeUpdate() == 1) {
                        claimed.add(new KillOutboxRow(
                                request,
                                KillOutboxStatus.IN_FLIGHT,
                                candidate.attemptCount() + 1,
                                Instant.ofEpochMilli(candidate.nextAttemptAtMs()),
                                Instant.ofEpochMilli(leaseUntilMs),
                                candidate.lastError()));
                    }
                }
            }
            connection.commit();
            return List.copyOf(claimed);
        } catch (SQLException | RuntimeException error) {
            connection.rollback();
            throw error;
        } finally {
            connection.setAutoCommit(originalAutoCommit);
        }
    }

    private void markDeadLetter(String eventId, String error, long nowMs) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(
                """
                UPDATE kill_outbox
                SET delivery_status = 'dead_letter', lease_until_ms = NULL,
                    last_error = ?, updated_at_ms = ?
                WHERE event_id = ?
                """)) {
            statement.setString(1, error);
            statement.setLong(2, nowMs);
            statement.setString(3, eventId);
            statement.executeUpdate();
        }
    }

    private CompletableFuture<Integer> count(String predicate) {
        return submit(() -> {
            try (Statement statement = connection.createStatement();
                    ResultSet result = statement.executeQuery(
                            "SELECT COUNT(*) FROM kill_outbox WHERE " + predicate)) {
                return result.getInt(1);
            }
        });
    }

    private void checkpointNow() throws SQLException {
        try (Statement statement = connection.createStatement()) {
            statement.execute("PRAGMA wal_checkpoint(TRUNCATE)");
        }
    }

    private String pragmaString(String name) throws SQLException {
        try (Statement statement = connection.createStatement();
                ResultSet result = statement.executeQuery("PRAGMA " + name)) {
            return result.getString(1);
        }
    }

    private int pragmaInt(String name) throws SQLException {
        try (Statement statement = connection.createStatement();
                ResultSet result = statement.executeQuery("PRAGMA " + name)) {
            return result.getInt(1);
        }
    }

    private <T> CompletableFuture<T> submit(CheckedSupplier<T> operation) {
        if (closed.get()) {
            return CompletableFuture.failedFuture(new IllegalStateException("SQLite outbox is closed"));
        }
        return submitInternal(operation);
    }

    private <T> CompletableFuture<T> submitInternal(CheckedSupplier<T> operation) {
        CompletableFuture<T> result = new CompletableFuture<>();
        try {
            writer.execute(() -> {
                try {
                    result.complete(operation.get());
                } catch (Throwable error) {
                    result.completeExceptionally(error);
                }
            });
        } catch (RejectedExecutionException error) {
            result.completeExceptionally(error);
        }
        return result;
    }

    @FunctionalInterface
    private interface CheckedSupplier<T> {
        T get() throws Exception;
    }

    private record RawRow(
            String eventId,
            String payloadJson,
            int attemptCount,
            long nextAttemptAtMs,
            String lastError) {}
}
