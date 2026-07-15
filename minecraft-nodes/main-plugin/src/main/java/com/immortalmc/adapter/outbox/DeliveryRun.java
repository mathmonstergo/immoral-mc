package com.immortalmc.adapter.outbox;

public record DeliveryRun(
        int claimed,
        int acknowledged,
        int retried,
        int deadLettered,
        boolean skipped) {
    public static DeliveryRun skippedRun() {
        return new DeliveryRun(0, 0, 0, 0, true);
    }
}
