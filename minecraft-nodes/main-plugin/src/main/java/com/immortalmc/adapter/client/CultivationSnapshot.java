package com.immortalmc.adapter.client;

public record CultivationSnapshot(
        int contractVersion,
        int currentLevel,
        String realmName,
        long currentProgress,
        long maxExp,
        long realizedTotal,
        long unrefinedReserve,
        long reserveCap,
        long revision,
        boolean progressFull,
        boolean reserveFull,
        boolean canAdvance) {
    public CultivationSnapshot {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported cultivation contract version");
        }
        if (currentLevel < 1 || currentLevel > 22) {
            throw new IllegalArgumentException("currentLevel is outside supported bounds");
        }
        if (realmName == null || realmName.isBlank()) {
            throw new IllegalArgumentException("realmName must be non-blank");
        }
        if (currentProgress < 0 || maxExp <= 0 || realizedTotal < 0 || unrefinedReserve < 0 || reserveCap < 0) {
            throw new IllegalArgumentException("Cultivation amounts are outside supported bounds");
        }
        if (currentProgress > maxExp) {
            throw new IllegalArgumentException("currentProgress cannot exceed maxExp");
        }
        if (revision < 0) {
            throw new IllegalArgumentException("revision must be non-negative");
        }
    }

    public double currentRatio() {
        return ratio(currentProgress, maxExp);
    }

    public double reserveRatio() {
        if (reserveCap == 0) {
            return unrefinedReserve > 0 ? 1.0 : 0.0;
        }
        return ratio(unrefinedReserve, reserveCap);
    }

    private static double ratio(long value, long maximum) {
        return Math.max(0.0, Math.min(1.0, (double) value / (double) maximum));
    }
}
