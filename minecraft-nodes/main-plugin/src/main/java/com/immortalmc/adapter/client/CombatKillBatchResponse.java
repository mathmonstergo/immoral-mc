package com.immortalmc.adapter.client;

import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

public record CombatKillBatchResponse(int contractVersion, List<CombatKillResult> results) {
    public CombatKillBatchResponse {
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported combat contract version");
        }
        results = List.copyOf(Objects.requireNonNull(results, "results"));
    }

    public CombatKillBatchResponse validateAgainst(List<CombatKillEventRequest> requests) {
        Objects.requireNonNull(requests, "requests");
        Set<UUID> requestedIds = new HashSet<>();
        for (CombatKillEventRequest request : requests) {
            requestedIds.add(request.eventId());
        }
        Set<UUID> resultIds = new HashSet<>();
        for (CombatKillResult result : results) {
            if (!resultIds.add(result.eventId())) {
                throw new IllegalArgumentException("Combat response contains duplicate event IDs");
            }
        }
        if (results.size() != requests.size() || !resultIds.equals(requestedIds)) {
            throw new IllegalArgumentException("Combat response event IDs do not match the request");
        }
        return this;
    }
}
