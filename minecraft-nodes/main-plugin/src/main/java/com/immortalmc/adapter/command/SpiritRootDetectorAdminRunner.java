package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.content.EntityInteractionEntity;
import com.immortalmc.adapter.content.EntityInteractionRegistry;
import com.immortalmc.adapter.gameplay.SpiritRootDetectionInteractionAction;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.List;
import java.util.Objects;
import java.util.function.Consumer;

public final class SpiritRootDetectorAdminRunner {
    private final EntityInteractionRegistry registry;
    private final SpiritRootDetectorAdminMessages messages;
    private final AdapterLogger logger;

    public SpiritRootDetectorAdminRunner(
            EntityInteractionRegistry registry,
            SpiritRootDetectorAdminMessages messages,
            AdapterLogger logger) {
        this.registry = Objects.requireNonNull(registry, "registry");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void createDetector(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_detector_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        if (source.entitySpawner().isEmpty()) {
            logger.warn("spirit_root_detector_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=spawner_missing");
            sendMessage.accept(messages.createUnavailable());
            return;
        }

        String id = registry.nextId(SpiritRootDetectionInteractionAction.ACTION);
        EntityInteractionEntity spawned = source.entitySpawner().orElseThrow().apply(id);
        EntityInteractionDefinition saved =
                registry.saveInteraction(id, SpiritRootDetectionInteractionAction.ACTION, spawned);
        logger.info("spirit_root_detector_created minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + saved.id()
                + " world="
                + saved.binding().worldName()
                + " entity_uuid="
                + saved.binding().entityUuid()
                + " entity_type="
                + saved.entityType()
                + " total_detectors="
                + registry.listByAction(SpiritRootDetectionInteractionAction.ACTION).size());
        sendMessage.accept(messages.created(saved, registry.listByAction(SpiritRootDetectionInteractionAction.ACTION).size()));
    }

    public void setLookedAtEntityAsDetector(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_detector_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        EntityInteractionEntity entity = source.lookedAtEntity().orElse(null);
        if (entity == null) {
            logger.warn("spirit_root_detector_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=target_missing");
            sendMessage.accept(messages.targetMissing());
            return;
        }

        EntityInteractionDefinition saved =
                registry.saveInteraction(SpiritRootDetectionInteractionAction.ACTION, entity);
        int totalDetectors = registry.listByAction(SpiritRootDetectionInteractionAction.ACTION).size();
        logger.info("spirit_root_detector_saved minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + saved.id()
                + " world="
                + saved.binding().worldName()
                + " entity_uuid="
                + saved.binding().entityUuid()
                + " entity_type="
                + saved.entityType()
                + " total_detectors="
                + totalDetectors);
        sendMessage.accept(messages.saved(saved, totalDetectors));
    }

    public void listDetectors(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");

        List<EntityInteractionDefinition> detectors =
                registry.listByAction(SpiritRootDetectionInteractionAction.ACTION);
        sendMessage.accept(messages.listHeader(detectors.size()));
        for (EntityInteractionDefinition detector : detectors) {
            sendMessage.accept(messages.listEntry(detector));
        }
    }

    public void removeLookedAtDetector(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_detector_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        EntityInteractionEntity entity = source.lookedAtEntity().orElse(null);
        if (entity == null) {
            logger.warn("spirit_root_detector_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=target_missing");
            sendMessage.accept(messages.targetMissing());
            return;
        }

        EntityInteractionDefinition removed = registry
                .removeInteraction(SpiritRootDetectionInteractionAction.ACTION, entity.binding())
                .orElse(null);
        if (removed == null) {
            logger.warn("spirit_root_detector_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " world="
                    + entity.binding().worldName()
                    + " entity_uuid="
                    + entity.binding().entityUuid()
                    + " reason=target_not_bound");
            sendMessage.accept(messages.notBound());
            return;
        }

        int totalDetectors = registry.listByAction(SpiritRootDetectionInteractionAction.ACTION).size();
        logger.info("spirit_root_detector_removed minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " interaction_id="
                + removed.id()
                + " world="
                + removed.binding().worldName()
                + " entity_uuid="
                + removed.binding().entityUuid()
                + " total_detectors="
                + totalDetectors);
        sendMessage.accept(messages.removed(removed, totalDetectors));
    }

    public void reload(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");

        int totalDetectors = registry.reload();
        int spiritRootDetectors = registry.listByAction(SpiritRootDetectionInteractionAction.ACTION).size();
        logger.info("entity_interaction_reloaded total_interactions="
                + totalDetectors
                + " spirit_root_detectors="
                + spiritRootDetectors);
        sendMessage.accept(messages.reloaded(spiritRootDetectors));
    }
}
