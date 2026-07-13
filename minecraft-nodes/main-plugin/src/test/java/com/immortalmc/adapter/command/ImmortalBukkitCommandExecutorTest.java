package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.citizens.CitizensNpcSelector;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;

class ImmortalBukkitCommandExecutorTest {
    @Test
    void completesQuestCommandsAndConfirmedProviderIds() {
        QuestProviderCatalogCache cache = new QuestProviderCatalogCache();
        cache.confirm(new QuestProviderCatalog(
                1,
                "sha256:catalog",
                List.of(
                        new QuestProviderTemplate("old-man", "老村民", List.of(), List.of()),
                        new QuestProviderTemplate("village-chief", "村长", List.of(), List.of()))));
        ImmortalBukkitCommandExecutor executor = new ImmortalBukkitCommandExecutor(
                commandService(),
                CitizensNpcResolver.unavailable(),
                CitizensNpcSelector.unavailable(),
                cache);

        assertEquals(List.of("quest"), executor.complete(new String[] {"qu"}));
        assertEquals(
                List.of("templates", "bind", "info", "list", "unbind", "reload"),
                executor.complete(new String[] {"quest", ""}));
        assertEquals(
                List.of("village-chief"),
                executor.complete(new String[] {"quest", "bind", "v"}));
    }

    private static ImmortalCommandService commandService() {
        HealthCommandMessages messages = new HealthCommandMessages();
        return new ImmortalCommandService(
                new ImmortalCommandHandler(),
                new HealthCommandRunner(
                        () -> CompletableFuture.completedFuture(
                                new HealthCheckResult("game-service", "ok", "0.1.0")),
                        messages,
                        new RecordingAdapterLogger(),
                        Runnable::run),
                messages);
    }
}
