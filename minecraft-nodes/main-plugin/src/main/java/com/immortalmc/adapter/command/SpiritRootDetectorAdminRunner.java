package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.SpiritRootDetectorRegistry;
import com.immortalmc.adapter.logging.AdapterLogger;
import java.util.Objects;
import java.util.function.Consumer;

public final class SpiritRootDetectorAdminRunner {
    private final SpiritRootDetectorRegistry registry;
    private final SpiritRootDetectorAdminMessages messages;
    private final AdapterLogger logger;

    public SpiritRootDetectorAdminRunner(
            SpiritRootDetectorRegistry registry,
            SpiritRootDetectorAdminMessages messages,
            AdapterLogger logger) {
        this.registry = Objects.requireNonNull(registry, "registry");
        this.messages = Objects.requireNonNull(messages, "messages");
        this.logger = Objects.requireNonNull(logger, "logger");
    }

    public void setLookedAtEntityAsDetector(ImmortalCommandSource source, Consumer<String> sendMessage) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(sendMessage, "sendMessage");

        if (source.minecraftUuid().isEmpty()) {
            logger.debug("spirit_root_detector_admin_rejected reason=console_sender");
            sendMessage.accept(messages.playerOnly());
            return;
        }
        EntityBinding binding = source.lookedAtEntity().orElse(null);
        if (binding == null) {
            logger.warn("spirit_root_detector_admin_rejected minecraft_uuid="
                    + source.minecraftUuid().orElseThrow()
                    + " reason=target_missing");
            sendMessage.accept(messages.targetMissing());
            return;
        }

        int totalDetectors = registry.saveDetector(binding);
        logger.info("spirit_root_detector_saved minecraft_uuid="
                + source.minecraftUuid().orElseThrow()
                + " world="
                + binding.worldName()
                + " entity_uuid="
                + binding.entityUuid()
                + " total_detectors="
                + totalDetectors);
        sendMessage.accept(messages.saved(binding, totalDetectors));
    }

    public void reload(Consumer<String> sendMessage) {
        Objects.requireNonNull(sendMessage, "sendMessage");

        int totalDetectors = registry.reload();
        logger.info("spirit_root_detector_reloaded total_detectors=" + totalDetectors);
        sendMessage.accept(messages.reloaded(totalDetectors));
    }
}
