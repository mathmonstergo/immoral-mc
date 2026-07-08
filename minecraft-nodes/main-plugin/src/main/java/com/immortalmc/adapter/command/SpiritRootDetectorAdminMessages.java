package com.immortalmc.adapter.command;

import com.immortalmc.adapter.content.EntityInteractionDefinition;

public final class SpiritRootDetectorAdminMessages {
    public String playerOnly() {
        return "Only players can manage spirit-root detector entities.";
    }

    public String targetMissing() {
        return "Look at an entity within range before selecting a spirit-root detector.";
    }

    public String createUnavailable() {
        return "This command source cannot create a spirit-root detector entity.";
    }

    public String created(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " created as "
                + detector.entityType()
                + " in "
                + detector.binding().worldName()
                + ". Total detectors: "
                + totalDetectors
                + ".";
    }

    public String saved(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " saved for entity "
                + detector.binding().entityUuid()
                + " in "
                + detector.binding().worldName()
                + ". Total detectors: "
                + totalDetectors
                + ".";
    }

    public String listHeader(int totalDetectors) {
        return "Spirit-root detectors: " + totalDetectors + " configured.";
    }

    public String listEntry(EntityInteractionDefinition detector) {
        return "- "
                + detector.id()
                + " "
                + detector.entityType()
                + " "
                + detector.binding().worldName()
                + "/"
                + detector.binding().entityUuid()
                + " protected="
                + detector.protectedEntity();
    }

    public String notBound() {
        return "The selected entity is not a spirit-root detector.";
    }

    public String removed(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " removed. Total detectors: "
                + totalDetectors
                + ".";
    }

    public String removedManaged(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " removed and entity deleted. Total detectors: "
                + totalDetectors
                + ".";
    }

    public String removedEntityMissing(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " removed, but the entity was already missing. Total detectors: "
                + totalDetectors
                + ".";
    }

    public String removedEntityDeleteUnavailable(EntityInteractionDefinition detector, int totalDetectors) {
        return "Spirit-root detector "
                + detector.id()
                + " removed, but this command source cannot delete the entity. Total detectors: "
                + totalDetectors
                + ".";
    }

    public String reloaded(int totalDetectors) {
        return "Spirit-root detector content reloaded: " + totalDetectors + " detector(s).";
    }
}
