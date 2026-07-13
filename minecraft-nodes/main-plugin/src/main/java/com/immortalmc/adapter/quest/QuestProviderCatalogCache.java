package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

public final class QuestProviderCatalogCache {
    private volatile QuestProviderCatalog confirmedCatalog;

    public void confirm(QuestProviderCatalog catalog) {
        confirmedCatalog = Objects.requireNonNull(catalog, "catalog");
    }

    public Optional<QuestProviderCatalog> snapshot() {
        return Optional.ofNullable(confirmedCatalog);
    }

    public Optional<QuestProviderTemplate> find(String providerId) {
        Objects.requireNonNull(providerId, "providerId");
        QuestProviderCatalog catalog = confirmedCatalog;
        if (catalog == null) {
            return Optional.empty();
        }
        return catalog.providers().stream()
                .filter(provider -> provider.providerId().equals(providerId))
                .findFirst();
    }

    public List<QuestProviderTemplate> providers() {
        QuestProviderCatalog catalog = confirmedCatalog;
        return catalog == null ? List.of() : catalog.providers();
    }

    public List<String> providerIds() {
        return providers().stream().map(QuestProviderTemplate::providerId).toList();
    }
}
