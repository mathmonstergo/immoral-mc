package com.immortalmc.adapter.targeting;

import com.immortalmc.adapter.content.EntityBinding;
import java.util.Objects;
import org.bukkit.util.BoundingBox;

public record EntityTargetCandidate(EntityBinding binding, BoundingBox boundingBox) {
    public EntityTargetCandidate {
        Objects.requireNonNull(binding, "binding");
        Objects.requireNonNull(boundingBox, "boundingBox");
    }
}
