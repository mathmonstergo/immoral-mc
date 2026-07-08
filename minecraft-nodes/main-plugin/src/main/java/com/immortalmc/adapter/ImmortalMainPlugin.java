package com.immortalmc.adapter;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.command.HealthCommandMessages;
import com.immortalmc.adapter.command.HealthCommandRunner;
import com.immortalmc.adapter.command.ImmortalBukkitCommandExecutor;
import com.immortalmc.adapter.command.ImmortalCommandHandler;
import com.immortalmc.adapter.command.ImmortalCommandService;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.command.SpiritRootCommandRunner;
import com.immortalmc.adapter.config.PluginSettings;
import com.immortalmc.adapter.event.ImmortalPlayerJoinListener;
import com.immortalmc.adapter.event.PlayerJoinLoginService;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.logging.PaperAdapterLogger;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.net.http.HttpClient;
import java.util.Objects;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class ImmortalMainPlugin extends JavaPlugin {
    @Override
    public void onEnable() {
        saveDefaultConfig();

        PluginSettings settings = PluginSettings.from(
                getConfig().getString("game-service.base-url", "http://127.0.0.1:8000"));
        AdapterLogger adapterLogger = new PaperAdapterLogger(getLogger());
        GameServiceClient gameServiceClient =
                new GameServiceClient(settings.gameServiceBaseUri(), HttpClient.newHttpClient());
        PlayerSessionCache sessionCache = new PlayerSessionCache();
        HealthCommandMessages messages = new HealthCommandMessages();
        HealthCommandRunner healthCommandRunner = new HealthCommandRunner(
                gameServiceClient::checkHealth,
                messages,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        SpiritRootCommandRunner spiritRootCommandRunner = new SpiritRootCommandRunner(
                gameServiceClient::detectSpiritRoot,
                sessionCache,
                new SpiritRootCommandMessages(),
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        ImmortalCommandService commandService = new ImmortalCommandService(
                new ImmortalCommandHandler(), healthCommandRunner, spiritRootCommandRunner, messages);
        ImmortalBukkitCommandExecutor commandExecutor = new ImmortalBukkitCommandExecutor(commandService);

        PluginCommand immortalCommand =
                Objects.requireNonNull(getCommand("immortal"), "Command 'immortal' is missing from plugin.yml");
        immortalCommand.setExecutor(commandExecutor);
        immortalCommand.setTabCompleter(commandExecutor);

        PlayerJoinLoginService playerJoinLoginService = new PlayerJoinLoginService(
                gameServiceClient::loginPlayer,
                sessionCache,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        getServer().getPluginManager().registerEvents(new ImmortalPlayerJoinListener(playerJoinLoginService), this);

        getLogger().info("ImmortalMC adapter enabled; Game Service base URL: " + settings.gameServiceBaseUri());
    }
}
