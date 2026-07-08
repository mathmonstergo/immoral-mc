package com.immortalmc.adapter.gameplay;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.interaction.EntityInteractionAction;
import com.immortalmc.adapter.presentation.SpiritRootParticlePresenter;
import java.util.Objects;

public final class SpiritRootDetectionInteractionAction implements EntityInteractionAction<BukkitEntityInteractionContext> {
    public static final String ACTION = "spirit-root-detect";
    private static final String LOG_EVENT_PREFIX = "spirit_root_detector";

    private final SpiritRootDetectionUseCase detectionUseCase;
    private final SpiritRootParticlePresenter particlePresenter;

    public SpiritRootDetectionInteractionAction(
            SpiritRootDetectionUseCase detectionUseCase,
            SpiritRootParticlePresenter particlePresenter) {
        this.detectionUseCase = Objects.requireNonNull(detectionUseCase, "detectionUseCase");
        this.particlePresenter = Objects.requireNonNull(particlePresenter, "particlePresenter");
    }

    @Override
    public void handle(EntityInteractionDefinition definition, BukkitEntityInteractionContext context) {
        Objects.requireNonNull(definition, "definition");
        Objects.requireNonNull(context, "context");
        detectionUseCase.detectForPlayer(
                context.player().getUniqueId(),
                LOG_EVENT_PREFIX,
                context.player()::sendMessage,
                result -> particlePresenter.play(context.player(), context.entity(), result.spiritRoot()));
    }
}
