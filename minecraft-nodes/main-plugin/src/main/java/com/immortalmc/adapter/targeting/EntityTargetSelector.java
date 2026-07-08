package com.immortalmc.adapter.targeting;

import com.immortalmc.adapter.content.EntityInteractionEntity;
import java.util.Collection;
import java.util.Objects;
import java.util.Optional;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

public final class EntityTargetSelector {
    private static final double TARGET_TOLERANCE = 0.12;

    private final double maxDistance;

    public EntityTargetSelector(double maxDistance) {
        if (maxDistance <= 0.0) {
            throw new IllegalArgumentException("maxDistance must be positive");
        }
        this.maxDistance = maxDistance;
    }

    public Optional<EntityInteractionEntity> select(
            Vector eyePosition,
            Vector viewDirection,
            Collection<EntityTargetCandidate> candidates) {
        Objects.requireNonNull(eyePosition, "eyePosition");
        Objects.requireNonNull(viewDirection, "viewDirection");
        Objects.requireNonNull(candidates, "candidates");

        Vector normalizedDirection = viewDirection.clone();
        if (normalizedDirection.lengthSquared() == 0.0) {
            return Optional.empty();
        }
        normalizedDirection.normalize();

        EntityInteractionEntity selected = null;
        double selectedDistance = Double.MAX_VALUE;
        for (EntityTargetCandidate candidate : candidates) {
            BoundingBox searchBox = candidate.boundingBox().clone().expand(TARGET_TOLERANCE);
            RayTraceResult hit = searchBox.rayTrace(eyePosition, normalizedDirection, maxDistance);
            if (hit == null) {
                continue;
            }
            double hitDistance = hit.getHitPosition().distance(eyePosition);
            if (hitDistance >= selectedDistance) {
                continue;
            }
            selected = candidate.entity();
            selectedDistance = hitDistance;
        }

        return Optional.ofNullable(selected);
    }
}
