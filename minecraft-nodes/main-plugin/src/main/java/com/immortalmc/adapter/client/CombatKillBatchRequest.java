package com.immortalmc.adapter.client;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public record CombatKillBatchRequest(int contractVersion, List<CombatKillEventRequest> events) {
    public CombatKillBatchRequest {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported combat contract version");
        }
        events = List.copyOf(Objects.requireNonNull(events, "events"));
        if (events.isEmpty() || events.size() > 200) {
            throw new IllegalArgumentException("Combat batch must contain 1 to 200 events");
        }
        Set<UUID> eventIds = new HashSet<>();
        for (CombatKillEventRequest event : events) {
            if (!eventIds.add(event.eventId())) {
                throw new IllegalArgumentException("Combat batch contains duplicate event IDs");
            }
        }
    }
}
