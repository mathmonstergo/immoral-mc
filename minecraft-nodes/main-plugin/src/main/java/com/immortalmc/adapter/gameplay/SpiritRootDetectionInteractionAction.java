package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.presentation.SpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.SpiritRootTitlePresenter;
import java.util.UUID;
import java.util.Objects;
import java.util.function.Consumer;

public final class SpiritRootDetectionInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "spirit-root-detect";
    public static final String QUEST_PROVIDER_ID_KEY = "quest-provider-id";
    private static final String LOG_EVENT_PREFIX = "spirit_root_detector";

    private final SpiritRootDetectionUseCase detectionUseCase;
    private final SpiritRootParticlePresenter particlePresenter;
    private final SpiritRootTitlePresenter titlePresenter;
    private final Consumer<UUID> questRefresher;

    public SpiritRootDetectionInteractionAction(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter) {
        this(detectionUseCase, particlePresenter, (player, root) -> {}, playerId -> {});
    }

    public SpiritRootDetectionInteractionAction(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter,
            SpiritRootTitlePresenter titlePresenter,
            Consumer<UUID> questRefresher) {
        this.detectionUseCase = Objects.requireNonNull(detectionUseCase, "detectionUseCase");
        this.particlePresenter = Objects.requireNonNull(particlePresenter, "particlePresenter");
        this.titlePresenter = Objects.requireNonNull(titlePresenter, "titlePresenter");
        this.questRefresher = Objects.requireNonNull(questRefresher, "questRefresher");
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
                    questRefresher.accept(context.player().getUniqueId());
                });
    }
}
