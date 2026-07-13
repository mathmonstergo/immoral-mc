package com.immortalmc.adapter;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.citizens.CitizensIntegrationHandle;
import com.immortalmc.adapter.citizens.CitizensIntegrationLoader;
import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.command.HealthCommandMessages;
import com.immortalmc.adapter.command.HealthCommandRunner;
import com.immortalmc.adapter.command.ImmortalBukkitCommandExecutor;
import com.immortalmc.adapter.command.ImmortalCommandHandler;
import com.immortalmc.adapter.command.ImmortalCommandService;
import com.immortalmc.adapter.command.NpcDialogueAdminMessages;
import com.immortalmc.adapter.command.NpcDialogueAdminRunner;
import com.immortalmc.adapter.command.QuestProviderAdminMessages;
import com.immortalmc.adapter.command.QuestProviderAdminRunner;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.command.SpiritRootCommandRunner;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminMessages;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminRunner;
import com.immortalmc.adapter.config.PluginSettings;
import com.immortalmc.adapter.content.BukkitConfigEntityInteractionRepository;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.dialogue.NpcDialogueAudience;
import com.immortalmc.adapter.dialogue.NpcDialoguePresenter;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.dialogue.YamlNpcDialogueRepository;
import com.immortalmc.adapter.event.EntityInteractionProtectionListener;
import com.immortalmc.adapter.event.ImmortalEntityInteractionListener;
import com.immortalmc.adapter.event.ImmortalPlayerJoinListener;
import com.immortalmc.adapter.event.ImmortalPlayerLifecycleListener;
import com.immortalmc.adapter.event.PlayerJoinLoginService;
import com.immortalmc.adapter.gameplay.NpcDialogueInteractionAction;
import com.immortalmc.adapter.gameplay.QuestProviderInteractionAction;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionInteractionAction;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionUseCase;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionActionRouter;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.logging.PaperAdapterLogger;
import com.immortalmc.adapter.presentation.BukkitQuestOfferLabelPresenter;
import com.immortalmc.adapter.presentation.BukkitQuestScoreboardView;
import com.immortalmc.adapter.presentation.BukkitSpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.BukkitSpiritRootTitlePresenter;
import com.immortalmc.adapter.presentation.QuestScoreboardRenderer;
import com.immortalmc.adapter.presentation.SpiritRootParticlePlanner;
import com.immortalmc.adapter.quest.QuestInteractionCache;
import com.immortalmc.adapter.quest.QuestNpcChunkIndex;
import com.immortalmc.adapter.quest.QuestNpcCoordinator;
import com.immortalmc.adapter.quest.QuestNpcSource;
import com.immortalmc.adapter.quest.QuestOfferSessionStore;
import com.immortalmc.adapter.quest.QuestPlayerPosition;
import com.immortalmc.adapter.quest.QuestProviderCatalogCache;
import com.immortalmc.adapter.quest.QuestRequestCoordinator;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.net.http.HttpClient;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.Sound;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

public final class ImmortalMainPlugin extends JavaPlugin {
    private PlayerSessionCache sessionCache;
    private QuestRequestCoordinator questRequests;
    private QuestNpcCoordinator questNpcCoordinator;
    private QuestScoreboardRenderer questScoreboards;
    private BukkitTask questCoordinatorTask;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        saveDialogueIfMissing("old-man.yml");
        saveDialogueIfMissing("first-steps.available.yml");
        saveDialogueIfMissing("first-steps.active.yml");
        saveDialogueIfMissing("first-steps.ready_to_turn_in.yml");
        saveDialogueIfMissing("first-steps.completed.yml");

        PluginSettings settings = PluginSettings.from(
                getConfig().getString("game-service.base-url", "http://127.0.0.1:8000"));
        AdapterLogger adapterLogger = new PaperAdapterLogger(getLogger());
        GameServiceClient gameServiceClient =
                new GameServiceClient(settings.gameServiceBaseUri(), HttpClient.newHttpClient());
        QuestProviderCatalogCache questProviderCatalog = new QuestProviderCatalogCache();
        sessionCache = new PlayerSessionCache();
        QuestInteractionCache questCache = new QuestInteractionCache();
        questRequests = new QuestRequestCoordinator(
                gameServiceClient,
                questCache,
                task -> getServer().getScheduler().runTask(this, task));
        QuestOfferSessionStore questOfferSessions = new QuestOfferSessionStore();
        questScoreboards = new QuestScoreboardRenderer(playerId -> new BukkitQuestScoreboardView(
                Objects.requireNonNull(getServer().getPlayer(playerId), "Quest scoreboard player is offline")));

        EntityInteractionRegistry entityInteractionRegistry = new EntityInteractionRegistry(
                new BukkitConfigEntityInteractionRepository(this));
        int loadedInteractions = entityInteractionRegistry.reload();
        NpcDialogueRegistry npcDialogueRegistry = new NpcDialogueRegistry(
                new YamlNpcDialogueRepository(getDataFolder().toPath().resolve("dialogues").toFile()));
        int loadedDialogues = npcDialogueRegistry.reload();
        boolean citizensEnabled = getServer().getPluginManager().isPluginEnabled("Citizens");

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
        NpcDialogueAdminRunner npcDialogueAdminRunner = new NpcDialogueAdminRunner(
                entityInteractionRegistry,
                npcDialogueRegistry,
                new NpcDialogueAdminMessages(),
                adapterLogger);
        PlayerJoinLoginService playerJoinLoginService = new PlayerJoinLoginService(
                gameServiceClient::loginPlayer,
                sessionCache,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task),
                result -> refreshLoginQuest(result, adapterLogger));
        BukkitSpiritRootParticlePresenter spiritRootParticlePresenter =
                new BukkitSpiritRootParticlePresenter(new SpiritRootParticlePlanner());
        BukkitSpiritRootTitlePresenter spiritRootTitlePresenter = new BukkitSpiritRootTitlePresenter();
        BukkitQuestOfferLabelPresenter questOfferLabelPresenter = new BukkitQuestOfferLabelPresenter(this);
        NpcDialoguePresenter npcDialoguePresenter = new NpcDialoguePresenter(
                (delayTicks, task) -> getServer().getScheduler().runTaskLater(this, task, delayTicks));

        EntityInteractionActionRouter<BukkitEntityInteractionContext> interactionRouter =
                new EntityInteractionActionRouter<>(Map.of(
                        SpiritRootDetectionInteractionAction.ACTION,
                        new SpiritRootDetectionInteractionAction(
                                spiritRootDetectionUseCase,
                                spiritRootParticlePresenter,
                                spiritRootTitlePresenter,
                                sessionCache,
                                questRequests,
                                questScoreboards::render),
                        QuestProviderInteractionAction.ACTION,
                        new QuestProviderInteractionAction(
                                sessionCache,
                                questRequests,
                                npcDialogueRegistry,
                                npcDialoguePresenter,
                                questOfferSessions,
                                questOfferLabelPresenter,
                                questScoreboards::render,
                                adapterLogger,
                                this::dialogueAudience,
                                Clock.systemUTC()),
                        NpcDialogueInteractionAction.ACTION,
                        new NpcDialogueInteractionAction(
                                npcDialogueRegistry,
                                npcDialoguePresenter,
                                adapterLogger,
                                this::dialogueAudience)));

        CitizensIntegrationHandle citizensIntegration = CitizensIntegrationLoader.enableIfAvailable(
                this,
                entityInteractionRegistry,
                interactionRouter,
                adapterLogger);
        CitizensNpcResolver citizensNpcResolver = citizensIntegration.resolver();
        QuestNpcSource questNpcSource = citizensIntegration.questNpcSource();
        QuestProviderAdminRunner questProviderAdminRunner = new QuestProviderAdminRunner(
                entityInteractionRegistry,
                questProviderCatalog,
                gameServiceClient::fetchQuestProviderCatalog,
                new QuestProviderAdminMessages(),
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        ImmortalCommandService commandService = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthCommandRunner,
                spiritRootCommandRunner,
                detectorAdminRunner,
                npcDialogueAdminRunner,
                questProviderAdminRunner,
                messages);
        QuestNpcChunkIndex questNpcIndex = new QuestNpcChunkIndex();
        long questScanIntervalTicks = positiveLong(
                getConfig().getLong("quest.scan-interval-ticks", 10L),
                10L);
        double questProximityRadius = positiveDouble(
                getConfig().getDouble("quest.proximity-radius", 6.0),
                6.0);
        int maxPlayersPerScan = positiveInt(
                getConfig().getInt("quest.max-players-per-scan", 100),
                100);
        questNpcCoordinator = new QuestNpcCoordinator(
                questNpcIndex,
                questCache,
                questRequests::refresh,
                (playerId, text) -> {
                    Player player = getServer().getPlayer(playerId);
                    if (player != null) {
                        player.sendMessage(text);
                    }
                },
                questOfferSessions,
                questProximityRadius,
                Duration.ofSeconds(60),
                maxPlayersPerScan);

        ImmortalBukkitCommandExecutor commandExecutor =
                new ImmortalBukkitCommandExecutor(
                        commandService,
                        citizensNpcResolver,
                        citizensIntegration.selector(),
                        questProviderCatalog);
        PluginCommand immortalCommand =
                Objects.requireNonNull(getCommand("immortal"), "Command 'immortal' is missing from plugin.yml");
        immortalCommand.setExecutor(commandExecutor);
        immortalCommand.setTabCompleter(commandExecutor);
        refreshQuestProviderCatalog(gameServiceClient, questProviderCatalog, adapterLogger);

        getServer().getPluginManager().registerEvents(new ImmortalPlayerJoinListener(playerJoinLoginService), this);
        getServer().getPluginManager().registerEvents(
                new ImmortalPlayerLifecycleListener(
                        this::cleanupPlayer,
                        questNpcCoordinator::clearPlayer),
                this);
        getServer().getPluginManager().registerEvents(
                new ImmortalEntityInteractionListener(
                        entityInteractionRegistry,
                        interactionRouter,
                        adapterLogger,
                        citizensNpcResolver),
                this);
        getServer().getPluginManager().registerEvents(
                new EntityInteractionProtectionListener(entityInteractionRegistry, citizensNpcResolver),
                this);

        questCoordinatorTask = getServer().getScheduler().runTaskTimer(this, () -> {
            questNpcIndex.replaceAll(questNpcSource.snapshot());
            questNpcCoordinator.tick(onlineQuestPlayers(), Instant.now());
        }, questScanIntervalTicks, questScanIntervalTicks);

        getLogger().info("ImmortalMC adapter enabled; Game Service base URL: "
                + settings.gameServiceBaseUri()
                + "; entity interactions loaded: "
                + loadedInteractions
                + "; NPC dialogues loaded: "
                + loadedDialogues
                + "; Citizens integration: "
                + (citizensEnabled ? "enabled" : "unavailable"));
    }

    @Override
    public void onDisable() {
        if (questCoordinatorTask != null) {
            questCoordinatorTask.cancel();
            questCoordinatorTask = null;
        }
        if (questRequests != null) {
            questRequests.clear();
        }
        if (questNpcCoordinator != null) {
            questNpcCoordinator.clear();
        }
        if (questScoreboards != null) {
            questScoreboards.clear();
        }
        if (sessionCache != null) {
            sessionCache.clear();
        }
    }

    private void refreshLoginQuest(PlayerLoginResult result, AdapterLogger logger) {
        questRequests
                .refresh(
                        result.account().minecraftUuid(),
                        result.account().accountId(),
                        result.currentLife().lifeId(),
                        "old-man")
                .whenComplete((state, error) -> {
                    if (error != null) {
                        logger.warn("quest_login_refresh_failure minecraft_uuid="
                                + result.account().minecraftUuid()
                                + " reason="
                                + error.getMessage());
                        return;
                    }
                    questScoreboards.render(result.account().minecraftUuid(), state.trackedQuest());
                });
    }

    private void refreshQuestProviderCatalog(
            GameServiceClient gameServiceClient,
            QuestProviderCatalogCache catalogCache,
            AdapterLogger logger) {
        gameServiceClient.fetchQuestProviderCatalog().whenComplete((catalog, error) ->
                getServer().getScheduler().runTask(this, () -> {
                    if (error != null) {
                        logger.warn("quest_provider_catalog_startup_refresh_failed reason=" + error.getMessage());
                        return;
                    }
                    catalogCache.confirm(catalog);
                    logger.info("quest_provider_catalog_startup_refreshed revision="
                            + catalog.revision()
                            + " providers="
                            + catalog.providers().size());
                }));
    }

    private void cleanupPlayer(UUID playerId) {
        sessionCache.remove(playerId);
        questRequests.clearPlayer(playerId);
        questNpcCoordinator.clearPlayer(playerId);
        questScoreboards.clearPlayer(playerId);
    }

    private List<QuestPlayerPosition> onlineQuestPlayers() {
        List<QuestPlayerPosition> players = new ArrayList<>();
        for (Player player : getServer().getOnlinePlayers()) {
            PlayerLoginResult session = sessionCache.findByMinecraftUuid(player.getUniqueId()).orElse(null);
            if (session == null) {
                continue;
            }
            var location = player.getLocation();
            players.add(new QuestPlayerPosition(
                    player.getUniqueId(),
                    session.account().accountId(),
                    session.currentLife().lifeId(),
                    player.getWorld().getUID(),
                    location.getX(),
                    location.getY(),
                    location.getZ(),
                    location.getBlockX() >> 4,
                    location.getBlockZ() >> 4));
        }
        return List.copyOf(players);
    }

    private NpcDialogueAudience dialogueAudience(Player player) {
        return new NpcDialogueAudience() {
            @Override
            public void sendMessage(String message) {
                player.sendMessage(message);
            }

            @Override
            public void playSound(String sound, float volume, float pitch) {
                player.playSound(player.getLocation(), resolveSound(sound), volume, pitch);
            }
        };
    }

    private void saveDialogueIfMissing(String fileName) {
        Path path = getDataFolder().toPath().resolve("dialogues").resolve(fileName);
        if (!Files.exists(path)) {
            saveResource("dialogues/" + fileName, false);
        }
    }

    private static long positiveLong(long value, long fallback) {
        return value > 0 ? value : fallback;
    }

    private static int positiveInt(int value, int fallback) {
        return value > 0 ? value : fallback;
    }

    private static double positiveDouble(double value, double fallback) {
        return value > 0 ? value : fallback;
    }

    private static Sound resolveSound(String sound) {
        NamespacedKey key = sound.contains(":")
                ? NamespacedKey.fromString(sound)
                : NamespacedKey.minecraft(sound.toLowerCase(Locale.ROOT).replace('_', '.'));
        Sound resolved = key == null ? null : Registry.SOUNDS.get(key);
        if (resolved == null) {
            throw new IllegalArgumentException("Unknown sound: " + sound);
        }
        return resolved;
    }
}
