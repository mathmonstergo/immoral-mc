package com.immortalmc.adapter;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.command.HealthCommandMessages;
import com.immortalmc.adapter.command.HealthCommandRunner;
import com.immortalmc.adapter.command.ImmortalBukkitCommandExecutor;
import com.immortalmc.adapter.command.ImmortalCommandHandler;
import com.immortalmc.adapter.command.ImmortalCommandService;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminMessages;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminRunner;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.command.SpiritRootCommandRunner;
import com.immortalmc.adapter.config.PluginSettings;
import com.immortalmc.adapter.content.BukkitConfigEntityInteractionRepository;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.event.EntityInteractionProtectionListener;
import com.immortalmc.adapter.event.ImmortalEntityInteractionListener;
import com.immortalmc.adapter.event.ImmortalPlayerJoinListener;
import com.immortalmc.adapter.event.PlayerJoinLoginService;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionInteractionAction;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionUseCase;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.logging.PaperAdapterLogger;
import com.immortalmc.adapter.presentation.BukkitSpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.SpiritRootParticlePlanner;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.net.http.HttpClient;
import java.util.Map;
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
        EntityInteractionRegistry entityInteractionRegistry = new EntityInteractionRegistry(
                new BukkitConfigEntityInteractionRepository(this));
        int loadedInteractions = entityInteractionRegistry.reload();
        HealthCommandMessages messages = new HealthCommandMessages();
        HealthCommandRunner healthCommandRunner = new HealthCommandRunner(
                gameServiceClient::checkHealth,
                messages,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        SpiritRootCommandMessages spiritRootMessages = new SpiritRootCommandMessages();
        SpiritRootDetectionUseCase spiritRootDetectionUseCase = new SpiritRootDetectionUseCase(
                gameServiceClient::detectSpiritRoot,
                sessionCache,
                spiritRootMessages,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        SpiritRootCommandRunner spiritRootCommandRunner = new SpiritRootCommandRunner(
                spiritRootDetectionUseCase,
                spiritRootMessages,
                adapterLogger);
        SpiritRootDetectorAdminRunner detectorAdminRunner = new SpiritRootDetectorAdminRunner(
                entityInteractionRegistry,
                new SpiritRootDetectorAdminMessages(),
                adapterLogger);
        ImmortalCommandService commandService = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthCommandRunner,
                spiritRootCommandRunner,
                detectorAdminRunner,
                messages);
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
        BukkitSpiritRootParticlePresenter spiritRootParticlePresenter =
                new BukkitSpiritRootParticlePresenter(new SpiritRootParticlePlanner());
        EntityInteractionActionRouter<BukkitEntityInteractionContext> interactionRouter =
                new EntityInteractionActionRouter<>(Map.of(
                        SpiritRootDetectionInteractionAction.ACTION,
                        new SpiritRootDetectionInteractionAction(
                                spiritRootDetectionUseCase,
                                spiritRootParticlePresenter)));
        getServer().getPluginManager().registerEvents(new ImmortalPlayerJoinListener(playerJoinLoginService), this);
        getServer().getPluginManager().registerEvents(
                new ImmortalEntityInteractionListener(
                        entityInteractionRegistry,
                        interactionRouter,
                        adapterLogger),
                this);
        getServer().getPluginManager().registerEvents(
                new EntityInteractionProtectionListener(entityInteractionRegistry),
                this);

        getLogger().info("ImmortalMC adapter enabled; Game Service base URL: "
                + settings.gameServiceBaseUri()
                + "; entity interactions loaded: "
                + loadedInteractions);
    }
}
