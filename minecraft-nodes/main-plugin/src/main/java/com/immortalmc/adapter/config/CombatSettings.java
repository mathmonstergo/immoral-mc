package com.immortalmc.adapter.config;

import java.nio.file.Path;
import java.time.Duration;
import java.util.Objects;
import org.bukkit.configuration.Configuration;

public record CombatSettings(
        String serverId,
        Duration maxSourceAge,
        int maxActiveTargets,
        Path outboxFile,
        int writerQueueCapacity,
        Duration busyTimeout,
        Duration normalDeliveryInterval,
        Duration highLoadDeliveryInterval,
        double tpsThreshold,
        int batchSize,
        int highLoadBatchSize,
        Duration maxPendingAge,
        Duration leaseDuration,
        int maxAttempts) {
    public static CombatSettings from(Configuration config) {
        Objects.requireNonNull(config, "config");
        String serverId = requiredText(config, "server-id");
        long maxSourceAgeSeconds = positiveLong(config, "combat.attribution.max-source-age-seconds");
        int maxActiveTargets = positiveInt(config, "combat.attribution.max-active-targets");
        String file = requiredText(config, "combat.outbox.file");
        Path outboxFile = Path.of(file).normalize();
        if (outboxFile.isAbsolute() || outboxFile.getNameCount() != 1
                || outboxFile.startsWith("..")) {
            throw new IllegalArgumentException("combat.outbox.file must be a local filename");
        }
        int writerQueueCapacity = positiveInt(config, "combat.outbox.writer-queue-capacity");
        long busyTimeoutMs = positiveLong(config, "combat.outbox.busy-timeout-ms");
        long normalIntervalMs = positiveLong(config, "combat.delivery.normal-interval-ms");
        long highLoadIntervalMs = positiveLong(config, "combat.delivery.high-load-interval-ms");
        double tpsThreshold = config.getDouble("combat.delivery.tps-threshold", Double.NaN);
        if (!Double.isFinite(tpsThreshold) || tpsThreshold <= 0.0) {
            throw new IllegalArgumentException("combat.delivery.tps-threshold must be positive");
        }
        int batchSize = positiveInt(config, "combat.delivery.batch-size");
        int highLoadBatchSize = positiveInt(config, "combat.delivery.high-load-batch-size");
        long maxPendingAgeSeconds = positiveLong(config, "combat.delivery.max-pending-age-seconds");
        long leaseSeconds = positiveLong(config, "combat.delivery.lease-seconds");
        int maxAttempts = positiveInt(config, "combat.delivery.max-attempts");
        return new CombatSettings(
                serverId,
                Duration.ofSeconds(maxSourceAgeSeconds),
                maxActiveTargets,
                outboxFile,
                writerQueueCapacity,
                Duration.ofMillis(busyTimeoutMs),
                Duration.ofMillis(normalIntervalMs),
                Duration.ofMillis(highLoadIntervalMs),
                tpsThreshold,
                batchSize,
                highLoadBatchSize,
                Duration.ofSeconds(maxPendingAgeSeconds),
                Duration.ofSeconds(leaseSeconds),
                maxAttempts);
    }

    private static String requiredText(Configuration config, String path) {
        String value = config.getString(path);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(path + " is required");
        }
        return value;
    }

    private static long positiveLong(Configuration config, String path) {
        long value = config.getLong(path, 0L);
        if (value <= 0L) {
            throw new IllegalArgumentException(path + " must be positive");
        }
        return value;
    }

    private static int positiveInt(Configuration config, String path) {
        int value = config.getInt(path, 0);
        if (value <= 0) {
            throw new IllegalArgumentException(path + " must be positive");
        }
        return value;
    }
}
