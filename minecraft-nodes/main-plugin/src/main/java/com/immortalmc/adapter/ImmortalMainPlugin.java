package com.immortalmc.adapter;

import com.immortalmc.adapter.client.GameServiceClient;
import com.immortalmc.adapter.citizens.CitizensIntegrationLoader;
import com.immortalmc.adapter.citizens.CitizensNpcResolver;
import com.immortalmc.adapter.command.HealthCommandMessages;
import com.immortalmc.adapter.command.HealthCommandRunner;
import com.immortalmc.adapter.command.ImmortalBukkitCommandExecutor;
import com.immortalmc.adapter.command.ImmortalCommandHandler;
import com.immortalmc.adapter.command.ImmortalCommandService;
import com.immortalmc.adapter.command.NpcDialogueAdminMessages;
import com.immortalmc.adapter.command.NpcDialogueAdminRunner;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminMessages;
import com.immortalmc.adapter.command.SpiritRootDetectorAdminRunner;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.command.SpiritRootCommandRunner;
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
import com.immortalmc.adapter.event.PlayerJoinLoginService;
import com.immortalmc.adapter.gameplay.NpcDialogueInteractionAction;
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
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import org.bukkit.NamespacedKey;
import org.bukkit.Registry;
import org.bukkit.Sound;
import org.bukkit.command.PluginCommand;
import org.bukkit.plugin.java.JavaPlugin;

public final class ImmortalMainPlugin extends JavaPlugin {
    @Override
    public void onEnable() {
        saveDefaultConfig();
        Path defaultDialogue = getDataFolder().toPath().resolve("dialogues/old-man.yml");
        if (!Files.exists(defaultDialogue)) {
            saveResource("dialogues/old-man.yml", false);
        }

        PluginSettings settings = PluginSettings.from(
                getConfig().getString("game-service.base-url", "http://127.0.0.1:8000"));
        AdapterLogger adapterLogger = new PaperAdapterLogger(getLogger());
        GameServiceClient gameServiceClient =
                new GameServiceClient(settings.gameServiceBaseUri(), HttpClient.newHttpClient());
        PlayerSessionCache sessionCache = new PlayerSessionCache();
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
        ImmortalCommandService commandService = new ImmortalCommandService(
                new ImmortalCommandHandler(),
                healthCommandRunner,
                spiritRootCommandRunner,
                detectorAdminRunner,
                npcDialogueAdminRunner,
                messages);
        PlayerJoinLoginService playerJoinLoginService = new PlayerJoinLoginService(
                gameServiceClient::loginPlayer,
                sessionCache,
                adapterLogger,
                task -> getServer().getScheduler().runTask(this, task));
        BukkitSpiritRootParticlePresenter spiritRootParticlePresenter =
                new BukkitSpiritRootParticlePresenter(new SpiritRootParticlePlanner());
        NpcDialoguePresenter npcDialoguePresenter = new NpcDialoguePresenter(
                (delayTicks, task) -> getServer().getScheduler().runTaskLater(this, task, delayTicks));
        EntityInteractionActionRouter<BukkitEntityInteractionContext> interactionRouter =
                new EntityInteractionActionRouter<>(Map.of(
                        SpiritRootDetectionInteractionAction.ACTION,
                        new SpiritRootDetectionInteractionAction(
                                spiritRootDetectionUseCase,
                                spiritRootParticlePresenter),
                        NpcDialogueInteractionAction.ACTION,
                        new NpcDialogueInteractionAction(
                                npcDialogueRegistry,
                                npcDialoguePresenter,
                                adapterLogger,
                                player -> new NpcDialogueAudience() {
                                    @Override
                                    public void sendMessage(String message) {
                                        player.sendMessage(message);
                                    }

                                    @Override
                                    public void playSound(String sound, float volume, float pitch) {
                                        player.playSound(player.getLocation(), resolveSound(sound), volume, pitch);
                                    }
                                })));
        CitizensNpcResolver citizensNpcResolver = CitizensIntegrationLoader.enableIfAvailable(
                this,
                entityInteractionRegistry,
                interactionRouter,
                adapterLogger);
        ImmortalBukkitCommandExecutor commandExecutor =
                new ImmortalBukkitCommandExecutor(commandService, citizensNpcResolver);
        PluginCommand immortalCommand =
                Objects.requireNonNull(getCommand("immortal"), "Command 'immortal' is missing from plugin.yml");
        immortalCommand.setExecutor(commandExecutor);
        immortalCommand.setTabCompleter(commandExecutor);

        getServer().getPluginManager().registerEvents(new ImmortalPlayerJoinListener(playerJoinLoginService), this);
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

        getLogger().info("ImmortalMC adapter enabled; Game Service base URL: "
                + settings.gameServiceBaseUri()
                + "; entity interactions loaded: "
                + loadedInteractions
                + "; NPC dialogues loaded: "
                + loadedDialogues
                + "; Citizens integration: "
                + (citizensEnabled ? "enabled" : "unavailable"));
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
