package com.immortalmc.adapter.outbox;

public record SqlitePragmas(
        String journalMode,
        int synchronous,
        boolean foreignKeys,
        int busyTimeoutMs) {}
