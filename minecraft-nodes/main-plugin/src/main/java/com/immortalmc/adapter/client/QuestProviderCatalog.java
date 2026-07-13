package com.immortalmc.adapter.client;

import java.util.List;
import java.util.Objects;

public record QuestProviderCatalog(
        int contractVersion,
        String revision,
        List<QuestProviderTemplate> providers) {
    public QuestProviderCatalog {
        Objects.requireNonNull(revision, "revision");
        providers = List.copyOf(Objects.requireNonNull(providers, "providers"));
        if (contractVersion != 1) {
            throw new IllegalArgumentException("Unsupported quest provider catalog contract: " + contractVersion);
        }
        if (revision.isBlank()) {
            throw new IllegalArgumentException("revision must not be blank");
        }
    }
}
