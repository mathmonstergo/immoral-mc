package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.dialogue.NpcDialogueAudience;
import com.immortalmc.adapter.dialogue.NpcDialoguePresenter;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import com.immortalmc.adapter.quest.QuestInteractionService;
import com.immortalmc.adapter.quest.QuestOfferLabel;
import com.immortalmc.adapter.quest.QuestOfferLabelPresenter;
import com.immortalmc.adapter.quest.QuestOfferSession;
import com.immortalmc.adapter.quest.QuestOfferSessionStore;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.time.Clock;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.CompletionException;
import java.util.function.BiConsumer;
import java.util.function.Function;
import org.bukkit.Location;
import org.bukkit.entity.Player;

public final class QuestProviderInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "quest-provider";
    public static final String PROVIDER_ID_KEY = "quest-provider-id";
    public static final String CITIZENS_NPC_UUID_KEY = "citizens-npc-uuid";

    private final PlayerSessionCache playerSessions;
    private final QuestInteractionService quests;
    private final NpcDialogueRegistry dialogues;
    private final NpcDialoguePresenter dialoguePresenter;
    private final QuestOfferSessionStore offerSessions;
    private final QuestOfferLabelPresenter labelPresenter;
    private final BiConsumer<UUID, TrackedQuestSnapshot> scoreboardRenderer;
    private final AdapterLogger logger;
    private final Function<Player, NpcDialogueAudience> audienceFactory;
    private final Clock clock;

    public QuestProviderInteractionAction(
            PlayerSessionCache playerSessions,
            QuestInteractionService quests,
            NpcDialogueRegistry dialogues,
            NpcDialoguePresenter dialoguePresenter,
            QuestOfferSessionStore offerSessions,
            QuestOfferLabelPresenter labelPresenter,
            BiConsumer<UUID, TrackedQuestSnapshot> scoreboardRenderer,
            AdapterLogger logger,
            Function<Player, NpcDialogueAudience> audienceFactory,
            Clock clock) {
        this.playerSessions = Objects.requireNonNull(playerSessions, "playerSessions");
        this.quests = Objects.requireNonNull(quests, "quests");
        this.dialogues = Objects.requireNonNull(dialogues, "dialogues");
        this.dialoguePresenter = Objects.requireNonNull(dialoguePresenter, "dialoguePresenter");
        this.offerSessions = Objects.requireNonNull(offerSessions, "offerSessions");
        this.labelPresenter = Objects.requireNonNull(labelPresenter, "labelPresenter");
        this.scoreboardRenderer = Objects.requireNonNull(scoreboardRenderer, "scoreboardRenderer");
        this.logger = Objects.requireNonNull(logger, "logger");
        this.audienceFactory = Objects.requireNonNull(audienceFactory, "audienceFactory");
        this.clock = Objects.requireNonNull(clock, "clock");
    }

    @Override
    public void handle(EntityInteractionDefinition definition, BukkitEntityInteractionContext context) {
        Player player = context.player();
        String providerId = definition.metadataValue(PROVIDER_ID_KEY).orElse(null);
        if (providerId == null) {
            logger.warn("quest_provider_rejected interaction_id=" + definition.id() + " reason=provider_id_missing");
            return;
        }
        PlayerLoginResult session = playerSessions.findByMinecraftUuid(player.getUniqueId()).orElse(null);
        if (session == null) {
            player.sendMessage("§c角色资料尚未加载，请稍后再试。");
            return;
        }

        QuestOfferSession pending = offerSessions.find(player.getUniqueId()).orElse(null);
        if (pending != null
                && pending.providerId().equals(providerId)
                && pending.phase() == QuestOfferSession.Phase.AWAITING_CONFIRMATION) {
            acceptPending(player, session, pending);
            return;
        }
        if (pending != null && pending.phase() == QuestOfferSession.Phase.PLAYING_OFFER) {
            player.sendMessage("§e任务接取中...");
            return;
        }

        quests.refresh(
                        player.getUniqueId(),
                        session.account().accountId(),
                        session.currentLife().lifeId(),
                        providerId)
                .whenComplete((state, error) -> {
                    if (error != null) {
                        player.sendMessage("§c任务服务暂时繁忙，请稍后重试。");
                        logFailure("quest_provider_refresh_failure", player, providerId, error);
                        return;
                    }
                    handleState(definition, context, session, providerId, state);
                });
    }

    private void handleState(
            EntityInteractionDefinition definition,
            BukkitEntityInteractionContext context,
            PlayerLoginResult session,
            String providerId,
            QuestInteractionState state) {
        QuestProviderSnapshot provider = state.providers().stream()
                .filter(item -> item.providerId().equals(providerId))
                .findFirst()
                .orElse(null);
        if (provider == null) {
            context.player().sendMessage("§c该角色当前没有可用任务。");
            return;
        }
        if (provider.directActionQuestId() == null) {
            if (provider.actionableQuestIds().size() > 1) {
                context.player().sendMessage("§e该角色有多个任务可处理，请稍后从任务列表选择。");
            }
            return;
        }
        ProviderQuestSnapshot quest = provider.quests().stream()
                .filter(item -> item.questId().equals(provider.directActionQuestId()))
                .findFirst()
                .orElse(null);
        if (quest == null) {
            return;
        }
        switch (quest.action()) {
            case "offer" -> startOffer(definition, context, providerId, quest);
            case "turn_in" -> turnIn(context.player(), session, providerId, quest);
            case "remind", "talk" -> playDialogue(context.player(), quest.dialogueKey());
            default -> {
                // No actionable quest for this provider.
            }
        }
    }

    private void startOffer(
            EntityInteractionDefinition definition,
            BukkitEntityInteractionContext context,
            String providerId,
            ProviderQuestSnapshot quest) {
        var dialogue = dialogues.find(quest.dialogueKey()).orElse(null);
        if (dialogue == null) {
            logger.warn("quest_offer_rejected quest_id=" + quest.questId() + " reason=dialogue_missing");
            return;
        }
        UUID npcId = definition.metadataValue(CITIZENS_NPC_UUID_KEY)
                .map(UUID::fromString)
                .orElse(context.entity().getUniqueId());
        Location location = context.entity().getLocation();
        QuestOfferLabel label = labelPresenter.show(context.player(), context.entity());
        QuestOfferSession offer = offerSessions.start(
                context.player().getUniqueId(),
                npcId,
                providerId,
                quest.questId(),
                context.entity().getWorld().getUID(),
                location.getX(),
                location.getY(),
                location.getZ(),
                clock.instant(),
                label);
        dialoguePresenter.play(
                dialogue,
                audienceFactory.apply(context.player()),
                () -> offerSessions.isCurrent(offer.token()),
                () -> offerSessions.markAwaitingConfirmation(offer.token(), clock.instant()));
    }

    private void acceptPending(Player player, PlayerLoginResult session, QuestOfferSession offer) {
        quests.accept(
                        player.getUniqueId(),
                        session.account().accountId(),
                        session.currentLife().lifeId(),
                        offer.questId(),
                        offer.providerId(),
                        UUID.randomUUID())
                .whenComplete((result, error) -> {
                    if (error != null) {
                        player.sendMessage("§c任务接取失败，请再次右键重试。");
                        logFailure("quest_accept_failure", player, offer.providerId(), error);
                        return;
                    }
                    offerSessions.cancel(offer.token());
                    scoreboardRenderer.accept(player.getUniqueId(), result.interactionState().trackedQuest());
                    player.sendMessage("§a已接取任务：§f" + result.quest().title());
                });
    }

    private void turnIn(
            Player player,
            PlayerLoginResult session,
            String providerId,
            ProviderQuestSnapshot quest) {
        quests.turnIn(
                        player.getUniqueId(),
                        session.account().accountId(),
                        session.currentLife().lifeId(),
                        quest.questId(),
                        providerId,
                        UUID.randomUUID())
                .whenComplete((result, error) -> {
                    if (error != null) {
                        player.sendMessage("§c任务交付失败，请稍后重试。");
                        logFailure("quest_turn_in_failure", player, providerId, error);
                        return;
                    }
                    scoreboardRenderer.accept(player.getUniqueId(), result.interactionState().trackedQuest());
                    playDialogue(player, result.quest().dialogueKey());
                });
    }

    private void playDialogue(Player player, String dialogueId) {
        if (dialogueId == null) {
            return;
        }
        dialogues.find(dialogueId).ifPresent(dialogue ->
                dialoguePresenter.play(dialogue, audienceFactory.apply(player)));
    }

    private void logFailure(String event, Player player, String providerId, Throwable error) {
        Throwable cause = unwrap(error);
        logger.warn(event
                + " minecraft_uuid="
                + player.getUniqueId()
                + " provider_id="
                + providerId
                + " reason="
                + cause.getMessage());
    }

    private static Throwable unwrap(Throwable error) {
        if ((error instanceof CompletionException) && error.getCause() != null) {
            return error.getCause();
        }
        return error;
    }
}
