package com.immortalmc.adapter.targeting;

import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Objects;
import org.bukkit.util.BoundingBox;

public record EntityTargetCandidate(EntityInteractionEntity entity, BoundingBox boundingBox) {
    public EntityTargetCandidate {
        Objects.requireNonNull(entity, "entity");
        Objects.requireNonNull(boundingBox, "boundingBox");
    }
}
