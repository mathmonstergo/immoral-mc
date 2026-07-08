package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityBinding;

public final class SpiritRootDetectorAdminMessages {
    public String playerOnly() {
        return "Only players can save spirit-root detector bindings.";
    }

    public String targetMissing() {
        return "Look at an entity within range before saving a spirit-root detector.";
    }

    public String saved(EntityBinding binding, int totalDetectors) {
        return "Spirit-root detector saved for entity "
                + binding.entityUuid()
                + " in "
                + binding.worldName()
                + ". Total detectors: "
                + totalDetectors
                + ".";
    }

    public String reloaded(int totalDetectors) {
        return "Spirit-root detector content reloaded: " + totalDetectors + " detector(s).";
    }
}
