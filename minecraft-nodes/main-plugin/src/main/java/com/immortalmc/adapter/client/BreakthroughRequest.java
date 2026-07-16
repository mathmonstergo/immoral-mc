package com.immortalmc.adapter.client;

public record BreakthroughRequest(int pillCount) {
    public BreakthroughRequest {
        if (pillCount < 1 || pillCount > 10) {
            throw new IllegalArgumentException("pillCount must be between one and ten");
        }
    }
}
