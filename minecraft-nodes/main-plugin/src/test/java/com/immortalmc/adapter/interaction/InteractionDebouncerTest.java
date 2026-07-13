package com.immortalmc.adapter.interaction;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

class InteractionDebouncerTest {
    @Test
    void rejectsSameKeyInsideWindowAndAllowsItAfterWindow() {
        AtomicLong now = new AtomicLong();
        InteractionDebouncer debouncer = new InteractionDebouncer(Duration.ofMillis(500), now::get);

        assertTrue(debouncer.tryAcquire("player:npc"));
        now.set(Duration.ofMillis(499).toNanos());
        assertFalse(debouncer.tryAcquire("player:npc"));
        now.set(Duration.ofMillis(500).toNanos());
        assertTrue(debouncer.tryAcquire("player:npc"));
    }

    @Test
    void allowsDifferentKeysInsideWindow() {
        InteractionDebouncer debouncer = new InteractionDebouncer(Duration.ofMillis(500), () -> 0L);

        assertTrue(debouncer.tryAcquire("player:npc-1"));
        assertTrue(debouncer.tryAcquire("player:npc-2"));
    }

    @Test
    void removesExpiredKeysDuringAcquisition() {
        AtomicLong now = new AtomicLong();
        InteractionDebouncer debouncer = new InteractionDebouncer(Duration.ofMillis(500), now::get);
        debouncer.tryAcquire("player:npc-1");

        now.set(Duration.ofMillis(500).toNanos());
        debouncer.tryAcquire("player:npc-2");

        assertTrue(debouncer.trackedKeyCount() == 1);
    }
}
