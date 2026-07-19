package com.immortalmc.adapter;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.combat.BukkitCombatAttributionListener;
import com.immortalmc.adapter.combat.CombatAttributionTracker;
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
import com.immortalmc.adapter.config.CombatSettings;
import com.immortalmc.adapter.config.PluginSettings;
import com.immortalmc.adapter.content.BukkitConfigEntityInteractionRepository;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.cultivation.CultivationAreaResolver;
import com.immortalmc.adapter.cultivation.CultivationCommandRunner;
import com.immortalmc.adapter.cultivation.SeclusionInventoryController;
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
import com.immortalmc.adapter.item.PhysicalItemCodec;
import com.immortalmc.adapter.item.PhysicalItemFactory;
import com.immortalmc.adapter.item.PhysicalItemReconciler;
import com.immortalmc.adapter.item.PhysicalPlayerInventory;
import com.immortalmc.adapter.item.PhysicalTechniqueListener;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.logging.PaperAdapterLogger;
import com.immortalmc.adapter.mythicmobs.MythicMobsIntegrationHandle;
import com.immortalmc.adapter.mythicmobs.MythicMobsIntegrationLoader;
import com.immortalmc.adapter.outbox.OutboxDeliveryPolicy;
import com.immortalmc.adapter.outbox.OutboxDeliveryWorker;
import com.immortalmc.adapter.outbox.SqliteKillOutbox;
import com.immortalmc.adapter.presentation.BukkitQuestOfferLabelPresenter;
import com.immortalmc.adapter.presentation.BukkitQuestScoreboardView;
import com.immortalmc.adapter.presentation.BukkitCultivationRewardPresenter;
import com.immortalmc.adapter.presentation.BukkitSpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.BukkitSpiritRootTitlePresenter;
import com.immortalmc.adapter.presentation.BetterHudCultivationIntegration;
import com.immortalmc.adapter.presentation.CultivationProjectionStore;
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
import com.immortalmc.adapter.quest.TrackedQuestRefreshCoordinator;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.storage.RegionalStorageInventoryController;
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
import java.util.function.Consumer;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.Sound;
import org.bukkit.command.PluginCommand;
import org.bukkit.entity.Player;
import org.bukkit.event.HandlerList;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitTask;

public final class ImmortalMainPlugin extends JavaPlugin {
    private PlayerSessionCache sessionCache;
    private PlayerJoinLoginService playerJoinLogins;
    private QuestRequestCoordinator questRequests;
    private QuestNpcCoordinator questNpcCoordinator;
    private QuestScoreboardRenderer questScoreboards;
    private TrackedQuestRefreshCoordinator trackedQuestRefreshes;
    private BukkitTask questCoordinatorTask;
    private BukkitCombatAttributionListener combatAttributionListener;
    private SqliteKillOutbox combatOutbox;
    private OutboxDeliveryWorker combatDeliveryWorker;
    private MythicMobsIntegrationHandle mythicMobsIntegration;
    private CultivationProjectionStore cultivationProjections;
    private BetterHudCultivationIntegration cultivationHud;
    private BukkitCultivationRewardPresenter cultivationRewardPresenter;
    private SeclusionInventoryController seclusionInventory;
    private PhysicalItemReconciler physicalItems;
    private PhysicalTechniqueListener techniqueManuals;
    private RegionalStorageInventoryController storageInventory;

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
        CombatSettings combatSettings = CombatSettings.from(getConfig());
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
        questScoreboards = new QuestScoreboardRenderer(playerId -> new BukkitQuestScoreboardView(
                Objects.requireNonNull(getServer().getPlayer(playerId), "Quest scoreboard player is offline")));
        trackedQuestRefreshes = new TrackedQuestRefreshCoordinator(
                gameServiceClient,
                sessionCache,
                task -> getServer().getScheduler().runTask(this, task),
                questScoreboards::render,
                adapterLogger);
        cultivationProjections = new CultivationProjectionStore();
        cultivationHud = BetterHudCultivationIntegration.create(this, cultivationProjections, adapterLogger);
        cultivationHud.start();
        cultivationRewardPresenter = new BukkitCultivationRewardPresenter(
                this,
                playerId -> refreshCultivation(playerId, gameServiceClient, adapterLogger),
                adapterLogger);
        Consumer<UUID> cultivationAndQuestRefresh = playerId -> {
            refreshCultivation(playerId, gameServiceClient, adapterLogger);
            trackedQuestRefreshes.refresh(playerId);
        };
        PhysicalItemCodec physicalItemCodec = new PhysicalItemCodec(this);
        PhysicalPlayerInventory physicalInventory = new PhysicalPlayerInventory(
                physicalItemCodec,
                new PhysicalItemFactory(physicalItemCodec));
        physicalItems = new PhysicalItemReconciler(
                gameServiceClient,
                sessionCache,
                physicalInventory,
                getServer()::getPlayer,
                task -> getServer().getScheduler().runTask(this, task),
                adapterLogger);
        techniqueManuals = new PhysicalTechniqueListener(
                gameServiceClient,
                sessionCache,
                physicalInventory,
                physicalItems::reconcile,
                cultivationAndQuestRefresh,
                task -> getServer().getScheduler().runTask(this, task),
                adapterLogger);
        CultivationAreaResolver cultivationAreas = CultivationAreaResolver.from(getConfig());
        storageInventory = new RegionalStorageInventoryController(
                this,
                gameServiceClient,
                sessionCache,
                cultivationAreas,
                physicalInventory,
                physicalItems::reconcile,
                task -> getServer().getScheduler().runTask(this, task),
                adapterLogger);
        seclusionInventory = new SeclusionInventoryController(
                this, gameServiceClient, sessionCache, cultivationAreas,
                cultivationAndQuestRefresh);
        CultivationCommandRunner cultivationCommands = new CultivationCommandRunner(
                this, gameServiceClient, sessionCache, seclusionInventory,
                cultivationAndQuestRefresh);
        CombatAttributionTracker combatTracker = new CombatAttributionTracker(
                combatSettings.maxSourceAge(),
                combatSettings.maxActiveTargets());
        combatOutbox = new SqliteKillOutbox(
                getDataFolder().toPath().resolve(combatSettings.outboxFile()),
                combatSettings.busyTimeout(),
                combatSettings.writerQueueCapacity(),
                Clock.systemUTC(),
                new ObjectMapper());
        combatDeliveryWorker = new OutboxDeliveryWorker(
                combatOutbox,
                requests -> gameServiceClient.sendCombatKills(requests),
                new OutboxDeliveryPolicy(
                        combatSettings.normalDeliveryInterval(),
                        combatSettings.highLoadDeliveryInterval(),
                        combatSettings.tpsThreshold(),
                        combatSettings.batchSize(),
                        combatSettings.highLoadBatchSize(),
                        combatSettings.maxPendingAge(),
                        combatSettings.leaseDuration(),
                        combatSettings.maxAttempts(),
                        Duration.ofSeconds(1),
                        Duration.ofSeconds(60)),
                Clock.systemUTC(),
                adapterLogger,
                cultivationRewardPresenter,
                task -> getServer().getScheduler().runTask(this, task),
                trackedQuestRefreshes::refresh);
        combatAttributionListener = new BukkitCombatAttributionListener(
                combatTracker,
                sessionCache,
                Clock.systemUTC(),
                combatSettings.maxSourceAge());
        getServer().getPluginManager().registerEvents(combatAttributionListener, this);
        mythicMobsIntegration = MythicMobsIntegrationLoader.enableIfAvailable(
                this,
                combatSettings.serverId(),
                combatTracker,
                snapshot -> combatOutbox.append(CombatKillEventRequest.fromSnapshot(snapshot)),
                adapterLogger,
                Clock.systemUTC());
        QuestOfferSessionStore questOfferSessions = new QuestOfferSessionStore();

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
        playerJoinLogins = new PlayerJoinLoginService(
                gameServiceClient::loginPlayer,
                sessionCache,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task),
                result -> {
                    cultivationProjections.beginLife(
                            result.account().minecraftUuid(),
                            result.currentLife().lifeId());
                    trackedQuestRefreshes.refresh(result.account().minecraftUuid());
                    refreshCultivation(
                            result.account().minecraftUuid(),
                            gameServiceClient,
                            adapterLogger);
                    physicalItems.reconcile(result.account().minecraftUuid());
                },
                playerId -> {
                    Player player = getServer().getPlayer(playerId);
                    return player != null && player.isOnline();
                });
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
                                trackedQuestRefreshes::refresh),
                        QuestProviderInteractionAction.ACTION,
                        new QuestProviderInteractionAction(
                                sessionCache,
                                questRequests,
                                npcDialogueRegistry,
                                npcDialoguePresenter,
                                questOfferSessions,
                                questOfferLabelPresenter,
                                trackedQuestRefreshes::publish,
                                adapterLogger,
                                this::dialogueAudience,
                                player -> physicalInventory.instanceIds(player.getInventory()),
                                physicalItems::reconcile,
                                playerId -> refreshCultivation(playerId, gameServiceClient, adapterLogger),
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
                        questProviderCatalog,
                        cultivationCommands::handle,
                        storageInventory::open);
        PluginCommand immortalCommand =
                Objects.requireNonNull(getCommand("immortal"), "Command 'immortal' is missing from plugin.yml");
        immortalCommand.setExecutor(commandExecutor);
        immortalCommand.setTabCompleter(commandExecutor);
        refreshQuestProviderCatalog(gameServiceClient, questProviderCatalog, adapterLogger);

        getServer().getPluginManager().registerEvents(new ImmortalPlayerJoinListener(playerJoinLogins), this);
        getServer().getPluginManager().registerEvents(cultivationRewardPresenter, this);
        getServer().getPluginManager().registerEvents(seclusionInventory, this);
        getServer().getPluginManager().registerEvents(techniqueManuals, this);
        getServer().getPluginManager().registerEvents(storageInventory, this);
        getServer().getPluginManager().registerEvents(
                new ImmortalPlayerLifecycleListener(
                        this::cleanupPlayer,
                        playerId -> {
                            questNpcCoordinator.clearPlayer(playerId);
                            storageInventory.clearPlayer(playerId);
                        }),
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

        combatDeliveryWorker.start(() -> getServer().getTPS()[0]);

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
                + (citizensEnabled ? "enabled" : "unavailable")
                + "; MythicMobs integration: "
                + (mythicMobsIntegration.available() ? "enabled" : "unavailable")
                + "; combat outbox: "
                + getDataFolder().toPath().resolve(combatSettings.outboxFile()));
    }

    @Override
    public void onDisable() {
        if (storageInventory != null) {
            storageInventory.close();
            storageInventory = null;
        }
        if (techniqueManuals != null) {
            techniqueManuals.close();
            techniqueManuals = null;
        }
        if (physicalItems != null) {
            physicalItems.close();
            physicalItems = null;
        }
        if (seclusionInventory != null) {
            seclusionInventory.close();
            seclusionInventory = null;
        }
        if (mythicMobsIntegration != null) {
            mythicMobsIntegration.close();
            mythicMobsIntegration = null;
        }
        if (combatAttributionListener != null) {
            HandlerList.unregisterAll(combatAttributionListener);
            combatAttributionListener = null;
        }
        if (combatDeliveryWorker != null) {
            combatDeliveryWorker.close();
            combatDeliveryWorker = null;
        }
        if (combatOutbox != null) {
            combatOutbox.close();
            combatOutbox = null;
        }
        if (questCoordinatorTask != null) {
            questCoordinatorTask.cancel();
            questCoordinatorTask = null;
        }
        if (playerJoinLogins != null) {
            playerJoinLogins.clear();
            playerJoinLogins = null;
        }
        if (questRequests != null) {
            questRequests.clear();
        }
        if (trackedQuestRefreshes != null) {
            trackedQuestRefreshes.clear();
            trackedQuestRefreshes = null;
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
        if (cultivationProjections != null) {
            cultivationProjections.clear();
        }
    }

    private void refreshCultivation(
            UUID playerId,
            GameServiceClient gameServiceClient,
            AdapterLogger logger) {
        PlayerLoginResult session = sessionCache.findByMinecraftUuid(playerId).orElse(null);
        if (session == null) {
            return;
        }
        UUID accountId = session.account().accountId();
        UUID lifeId = session.currentLife().lifeId();
        gameServiceClient.fetchCultivation(accountId).whenComplete((snapshot, error) ->
                getServer().getScheduler().runTask(this, () -> {
                    if (error != null) {
                        logger.warn("cultivation_projection_refresh_failed player_uuid="
                                + playerId
                                + " account_id="
                                + accountId
                                + " reason="
                                + error.getMessage());
                        return;
                    }
                    PlayerLoginResult current = sessionCache.findByMinecraftUuid(playerId).orElse(null);
                    if (current == null
                            || !current.account().accountId().equals(accountId)
                            || !current.currentLife().lifeId().equals(lifeId)) {
                        return;
                    }
                    cultivationProjections.confirm(playerId, lifeId, snapshot);
                    cultivationHud.refresh(playerId);
                }));
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
        if (playerJoinLogins != null) {
            playerJoinLogins.invalidate(playerId);
        }
        cultivationHud.remove(playerId);
        cultivationProjections.remove(playerId);
        if (techniqueManuals != null) {
            techniqueManuals.clearPlayer(playerId);
        }
        if (physicalItems != null) {
            physicalItems.clearPlayer(playerId);
        }
        if (storageInventory != null) {
            storageInventory.clearPlayer(playerId);
        }
        sessionCache.remove(playerId);
        questRequests.clearPlayer(playerId);
        trackedQuestRefreshes.clearPlayer(playerId);
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
