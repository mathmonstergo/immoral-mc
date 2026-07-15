package com.immortalmc.adapter.outbox;

import java.time.Duration;
import java.util.Objects;
import java.util.concurrent.ThreadLocalRandom;
import java.util.function.DoubleSupplier;

public final class OutboxDeliveryPolicy {
    private final Duration normalInterval;
    private final Duration highLoadInterval;
    private final double tpsThreshold;
    private final int normalBatchSize;
    private final int highLoadBatchSize;
    private final Duration maxPendingAge;
    private final Duration leaseDuration;
    private final int maxAttempts;
    private final Duration baseRetryDelay;
    private final Duration maxRetryDelay;
    private final DoubleSupplier retryJitter;

    public OutboxDeliveryPolicy(
            Duration normalInterval,
            Duration highLoadInterval,
            double tpsThreshold,
            int normalBatchSize,
            int highLoadBatchSize,
            Duration maxPendingAge,
            Duration leaseDuration,
            int maxAttempts,
            Duration baseRetryDelay,
            Duration maxRetryDelay) {
        this(
                normalInterval,
                highLoadInterval,
                tpsThreshold,
                normalBatchSize,
                highLoadBatchSize,
                maxPendingAge,
                leaseDuration,
                maxAttempts,
                baseRetryDelay,
                maxRetryDelay,
                () -> ThreadLocalRandom.current().nextDouble(0.5, 1.0));
    }

    OutboxDeliveryPolicy(
            Duration normalInterval,
            Duration highLoadInterval,
            double tpsThreshold,
            int normalBatchSize,
            int highLoadBatchSize,
            Duration maxPendingAge,
            Duration leaseDuration,
            int maxAttempts,
            Duration baseRetryDelay,
            Duration maxRetryDelay,
            DoubleSupplier retryJitter) {
        this.normalInterval = positive(normalInterval, "normalInterval");
        this.highLoadInterval = positive(highLoadInterval, "highLoadInterval");
        if (!Double.isFinite(tpsThreshold) || tpsThreshold <= 0.0) {
            throw new IllegalArgumentException("tpsThreshold must be positive and finite");
        }
        this.tpsThreshold = tpsThreshold;
        if (normalBatchSize <= 0 || highLoadBatchSize <= 0) {
            throw new IllegalArgumentException("batch sizes must be positive");
        }
        this.normalBatchSize = normalBatchSize;
        this.highLoadBatchSize = highLoadBatchSize;
        this.maxPendingAge = positive(maxPendingAge, "maxPendingAge");
        this.leaseDuration = positive(leaseDuration, "leaseDuration");
        if (maxAttempts <= 0) {
            throw new IllegalArgumentException("maxAttempts must be positive");
        }
        this.maxAttempts = maxAttempts;
        this.baseRetryDelay = positive(baseRetryDelay, "baseRetryDelay");
        this.maxRetryDelay = positive(maxRetryDelay, "maxRetryDelay");
        if (maxRetryDelay.compareTo(baseRetryDelay) < 0) {
            throw new IllegalArgumentException("maxRetryDelay must not be below baseRetryDelay");
        }
        this.retryJitter = Objects.requireNonNull(retryJitter, "retryJitter");
    }

    public Duration nextDelay(double tps, Duration oldestPendingAge) {
        if (oldestPendingAge.compareTo(maxPendingAge) >= 0) {
            return Duration.ZERO;
        }
        return isHighLoad(tps) ? highLoadInterval : normalInterval;
    }

    public int batchSize(double tps) {
        return isHighLoad(tps) ? highLoadBatchSize : normalBatchSize;
    }

    public Duration leaseDuration() {
        return leaseDuration;
    }

    public int maxAttempts() {
        return maxAttempts;
    }

    public Duration retryDelay(int attemptCount) {
        if (attemptCount <= 0) {
            throw new IllegalArgumentException("attemptCount must be positive");
        }
        long multiplier = 1L << Math.min(attemptCount - 1, 30);
        Duration candidate = baseRetryDelay.multipliedBy(multiplier);
        Duration capped = candidate.compareTo(maxRetryDelay) > 0 ? maxRetryDelay : candidate;
        double jitter = retryJitter.getAsDouble();
        if (!Double.isFinite(jitter) || jitter < 0.5 || jitter > 1.0) {
            throw new IllegalStateException("retry jitter must be between 0.5 and 1.0");
        }
        return Duration.ofMillis(Math.max(1L, (long) (capped.toMillis() * jitter)));
    }

    private boolean isHighLoad(double tps) {
        return !Double.isFinite(tps) || tps < tpsThreshold;
    }

    private static Duration positive(Duration value, String name) {
        if (value == null || value.isNegative() || value.isZero()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
    }
}
