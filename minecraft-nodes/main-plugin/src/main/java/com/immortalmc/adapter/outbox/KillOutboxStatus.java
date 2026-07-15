package com.immortalmc.adapter.outbox;

public enum KillOutboxStatus {
    PENDING("pending"),
    IN_FLIGHT("in_flight"),
    DEAD_LETTER("dead_letter");

    private final String databaseValue;

    KillOutboxStatus(String databaseValue) {
        this.databaseValue = databaseValue;
    }

    public String databaseValue() {
        return databaseValue;
    }
}
