package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.presentation.SpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.SpiritRootTitlePresenter;
import com.immortalmc.adapter.quest.QuestInteractionService;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.util.UUID;
import java.util.function.BiConsumer;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import java.util.Objects;

public final class SpiritRootDetectionInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "spirit-root-detect";
    public static final String QUEST_PROVIDER_ID_KEY = "quest-provider-id";
    private static final String LOG_EVENT_PREFIX = "spirit_root_detector";

    private final SpiritRootDetectionUseCase detectionUseCase;
    private final SpiritRootParticlePresenter particlePresenter;
    private final SpiritRootTitlePresenter titlePresenter;
    private final PlayerSessionCache sessionCache;
    private final QuestInteractionService quests;
    private final BiConsumer<UUID, TrackedQuestSnapshot> scoreboardRenderer;

    public SpiritRootDetectionInteractionAction(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter) {
        this(detectionUseCase, particlePresenter, (player, root) -> {}, null, null, (playerId, tracked) -> {});
    }

    public SpiritRootDetectionInteractionAction(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter,
            SpiritRootTitlePresenter titlePresenter,
            PlayerSessionCache sessionCache,
            QuestInteractionService quests,
            BiConsumer<UUID, TrackedQuestSnapshot> scoreboardRenderer) {
        this.detectionUseCase = Objects.requireNonNull(detectionUseCase, "detectionUseCase");
        this.particlePresenter = Objects.requireNonNull(particlePresenter, "particlePresenter");
        this.titlePresenter = Objects.requireNonNull(titlePresenter, "titlePresenter");
        this.sessionCache = sessionCache;
        this.quests = quests;
        this.scoreboardRenderer = Objects.requireNonNull(scoreboardRenderer, "scoreboardRenderer");
    }

    @Override
    public void handle(EntityInteractionDefinition definition, BukkitEntityInteractionContext context) {
        Objects.requireNonNull(definition, "definition");
        Objects.requireNonNull(context, "context");
        detectionUseCase.detectForPlayer(
                context.player().getUniqueId(),
                LOG_EVENT_PREFIX,
                context.player()::sendMessage,
                result -> {
                    particlePresenter.play(context.player(), context.entity(), result.spiritRoot());
                    titlePresenter.show(context.player(), result.spiritRoot());
                    refreshQuest(definition, context);
                });
    }

    private void refreshQuest(
            EntityInteractionDefinition definition,
            BukkitEntityInteractionContext context) {
        if (sessionCache == null || quests == null) {
            return;
        }
        var session = sessionCache.findByMinecraftUuid(context.player().getUniqueId()).orElse(null);
        if (session == null) {
            return;
        }
        String providerId = definition.metadataValue(QUEST_PROVIDER_ID_KEY).orElse("old-man");
        quests.refresh(
                        context.player().getUniqueId(),
                        session.account().accountId(),
                        session.currentLife().lifeId(),
                        providerId)
                .thenAccept(state -> scoreboardRenderer.accept(
                        context.player().getUniqueId(),
                        state.trackedQuest()));
    }
}
