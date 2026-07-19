package com.immortalmc.adapter.command;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.HealthCheckResult;
import com.immortalmc.adapter.client.QuestProviderCatalog;
import com.immortalmc.adapter.client.QuestProviderTemplate;
import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.citizens.CitizensNpcSelector;
import com.immortalmc.adapter.cultivation.CultivationCommandRunner;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

class ImmortalBukkitCommandExecutorTest {
    @Test
    void requiresPublicCultivationPermissionForPlayerCultivationCommands() {
        ImmortalCommandService commandService = mock(ImmortalCommandService.class);
        CultivationCommandRunner cultivationCommands = mock(CultivationCommandRunner.class);
        ImmortalBukkitCommandExecutor executor = executor(commandService, cultivationCommands);
        CommandSender sender = mock(CommandSender.class);

        executor.onCommand(sender, mock(Command.class), "immortal", new String[] {"seclusion"});

        verify(sender).hasPermission("immortalmc.cultivation");
        verify(sender).sendMessage("你没有使用修炼命令的权限。");
        verify(cultivationCommands, never()).handle(sender, new String[] {"seclusion"});
        verify(commandService, never()).execute(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    void dispatchesCultivationCommandWhenPublicPermissionIsGranted() {
        ImmortalCommandService commandService = mock(ImmortalCommandService.class);
        CultivationCommandRunner cultivationCommands = mock(CultivationCommandRunner.class);
        ImmortalBukkitCommandExecutor executor = executor(commandService, cultivationCommands);
        CommandSender sender = mock(CommandSender.class);
        when(sender.hasPermission("immortalmc.cultivation")).thenReturn(true);
        when(cultivationCommands.handle(sender, new String[] {"breakthrough", "1"})).thenReturn(true);

        executor.onCommand(
                sender,
                mock(Command.class),
                "immortal",
                new String[] {"breakthrough", "1"});

        verify(cultivationCommands).handle(sender, new String[] {"breakthrough", "1"});
        verify(commandService, never()).execute(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

    @Test
    void retainsAdminPermissionForExistingOperations() {
        ImmortalCommandService commandService = mock(ImmortalCommandService.class);
        CultivationCommandRunner cultivationCommands = mock(CultivationCommandRunner.class);
        ImmortalBukkitCommandExecutor executor = executor(commandService, cultivationCommands);
        CommandSender sender = mock(CommandSender.class);

        executor.onCommand(sender, mock(Command.class), "immortal", new String[] {"health"});

        verify(sender).hasPermission("immortalmc.command");
        verify(sender).sendMessage("你没有使用管理命令的权限。");
        verify(commandService, never()).execute(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
    }

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
                cache,
                (sender, args) -> false,
                player -> {});

        assertEquals(List.of("quest"), executor.complete(new String[] {"qu"}));
        assertEquals(
                List.of("templates", "bind", "info", "list", "unbind", "reload"),
                executor.complete(new String[] {"quest", ""}));
        assertEquals(
                List.of("village-chief"),
                executor.complete(new String[] {"quest", "bind", "v"}));
    }

    @Test
    void opensStorageThroughRequiredCommandBoundary() {
        ImmortalCommandService commandService = mock(ImmortalCommandService.class);
        Player player = mock(Player.class);
        @SuppressWarnings("unchecked")
        java.util.function.Consumer<Player> storageOpener = mock(java.util.function.Consumer.class);
        when(player.hasPermission("immortalmc.storage")).thenReturn(true);
        ImmortalBukkitCommandExecutor executor = new ImmortalBukkitCommandExecutor(
                commandService,
                CitizensNpcResolver.unavailable(),
                CitizensNpcSelector.unavailable(),
                new QuestProviderCatalogCache(),
                (sender, args) -> false,
                storageOpener);

        executor.onCommand(player, mock(Command.class), "immortal", new String[] {"storage"});

        verify(storageOpener).accept(player);
        verify(commandService, never()).execute(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any());
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

    private static ImmortalBukkitCommandExecutor executor(
            ImmortalCommandService commandService,
            CultivationCommandRunner cultivationCommands) {
        return new ImmortalBukkitCommandExecutor(
                commandService,
                CitizensNpcResolver.unavailable(),
                CitizensNpcSelector.unavailable(),
                new QuestProviderCatalogCache(),
                cultivationCommands::handle,
                player -> {});
    }
}
