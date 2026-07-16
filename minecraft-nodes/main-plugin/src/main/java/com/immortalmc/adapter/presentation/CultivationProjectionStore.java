package com.immortalmc.adapter.presentation;

import com.immortalmc.adapter.client.CultivationSnapshot;
import java.util.Objects;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.concurrent.atomic.AtomicBoolean;

public final class CultivationProjectionStore {
    private static final Projection DISABLED = new Projection(
            false,
            0,
            0,
            "",
            0,
            0,
            0,
            0,
            0,
            false,
            false,
            false,
            0.0,
            0.0);

    private final ConcurrentMap<UUID, LifeProjection> projections = new ConcurrentHashMap<>();

    public void beginLife(UUID playerId, UUID lifeId) {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(lifeId, "lifeId");
        projections.compute(playerId, (ignored, current) ->
                current != null && current.lifeId().equals(lifeId)
                        ? current
                        : new LifeProjection(lifeId, DISABLED));
    }

    public boolean confirm(UUID playerId, UUID lifeId, CultivationSnapshot snapshot) {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(lifeId, "lifeId");
        Objects.requireNonNull(snapshot, "snapshot");
        Projection confirmed = Projection.from(snapshot);
        AtomicBoolean changed = new AtomicBoolean();
        projections.compute(playerId, (ignored, current) -> {
            if (current == null || !current.lifeId().equals(lifeId)) {
                return current;
            }
            if (current.projection().enabled()
                    && current.projection().revision() >= confirmed.revision()) {
                return current;
            }
            changed.set(true);
            return new LifeProjection(lifeId, confirmed);
        });
        return changed.get();
    }

    public Projection snapshot(UUID playerId) {
        LifeProjection projection = projections.get(Objects.requireNonNull(playerId, "playerId"));
        return projection == null ? DISABLED : projection.projection();
    }

    public void remove(UUID playerId) {
        projections.remove(Objects.requireNonNull(playerId, "playerId"));
    }

    public void clear() {
        projections.clear();
    }

    private record LifeProjection(UUID lifeId, Projection projection) {}

    public record Projection(
            boolean enabled,
            long revision,
            int currentLevel,
            String realmName,
            long currentProgress,
            long maxExp,
            long realizedTotal,
            long unrefinedReserve,
            long reserveCap,
            boolean progressFull,
            boolean reserveFull,
            boolean canAdvance,
            double currentRatio,
            double reserveRatio) {
        private static Projection from(CultivationSnapshot snapshot) {
            return new Projection(
                    true,
                    snapshot.revision(),
                    snapshot.currentLevel(),
                    snapshot.realmName(),
                    snapshot.currentProgress(),
                    snapshot.maxExp(),
                    snapshot.realizedTotal(),
                    snapshot.unrefinedReserve(),
                    snapshot.reserveCap(),
                    snapshot.progressFull(),
                    snapshot.reserveFull(),
                    snapshot.canAdvance(),
                    snapshot.currentRatio(),
                    snapshot.reserveRatio());
        }
    }
}
