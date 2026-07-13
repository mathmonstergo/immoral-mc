package com.immortalmc.adapter.quest;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import java.util.List;
import org.junit.jupiter.api.Test;

class QuestProviderCatalogCacheTest {
    @Test
    void exposesOnlyTheLastConfirmedCatalogForLookupAndCompletion() {
        QuestProviderCatalogCache cache = new QuestProviderCatalogCache();

        assertTrue(cache.snapshot().isEmpty());
        assertEquals(List.of(), cache.providerIds());

        cache.confirm(new QuestProviderCatalog(
                1,
                "sha256:first",
                List.of(new QuestProviderTemplate("old-man", "老村民", List.of("first-steps"), List.of()))));
        cache.confirm(new QuestProviderCatalog(
                1,
                "sha256:second",
                List.of(new QuestProviderTemplate("village-chief", "村长", List.of(), List.of("help")))));

        assertEquals("sha256:second", cache.snapshot().orElseThrow().revision());
        assertEquals(List.of("village-chief"), cache.providerIds());
        assertEquals("村长", cache.find("village-chief").orElseThrow().displayName());
        assertTrue(cache.find("old-man").isEmpty());
    }
}
