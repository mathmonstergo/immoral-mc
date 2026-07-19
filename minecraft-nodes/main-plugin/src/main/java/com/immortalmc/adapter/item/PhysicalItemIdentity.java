package com.immortalmc.adapter.item;

import java.util.Objects;
import java.util.Optional;
import java.util.UUID;

public record PhysicalItemIdentity(
        UUID itemInstanceId,
        String itemCode,
        Optional<String> techniqueId,
        Optional<Integer> techniqueVersion) {
    public PhysicalItemIdentity {
        Objects.requireNonNull(itemInstanceId, "itemInstanceId");
        itemCode = requireText(itemCode, "itemCode");
        techniqueId = Objects.requireNonNull(techniqueId, "techniqueId")
                .map(value -> requireText(value, "techniqueId"));
        techniqueVersion = Objects.requireNonNull(techniqueVersion, "techniqueVersion");
        if (techniqueId.isPresent() != techniqueVersion.isPresent()) {
            throw new IllegalArgumentException("techniqueId and techniqueVersion must both be present or absent");
        }
        techniqueVersion.ifPresent(version -> {
            if (version <= 0) {
                throw new IllegalArgumentException("techniqueVersion must be positive");
            }
        });
    }

    public static PhysicalItemIdentity item(UUID itemInstanceId, String itemCode) {
        return new PhysicalItemIdentity(itemInstanceId, itemCode, Optional.empty(), Optional.empty());
    }

    public static PhysicalItemIdentity techniqueManual(
            UUID itemInstanceId,
            String itemCode,
            String techniqueId,
            int techniqueVersion) {
        return new PhysicalItemIdentity(
                itemInstanceId,
                itemCode,
                Optional.of(techniqueId),
                Optional.of(techniqueVersion));
    }

    public boolean isTechniqueManual() {
        return techniqueId.isPresent();
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank");
        }
        return value;
    }
}
