package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.dialogue.NpcDialogueText;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

public final class QuestNpcCoordinator {
    private final QuestNpcChunkIndex index;
    private final QuestInteractionCache cache;
    private final Refresher refresher;
    private final BarkSink barkSink;
    private final QuestOfferSessionStore sessions;
    private final double radiusSquared;
    private final Duration fallbackCooldown;
    private final int maxPlayersPerTick;
    private final Map<UUID, Set<UUID>> insideNpcIdsByPlayer = new HashMap<>();
    private final Map<CooldownKey, Instant> cooldowns = new HashMap<>();
    private int playerCursor;

    public QuestNpcCoordinator(
            QuestNpcChunkIndex index,
            QuestInteractionCache cache,
            Refresher refresher,
            BarkSink barkSink,
            QuestOfferSessionStore sessions,
            double radius,
            Duration fallbackCooldown,
            int maxPlayersPerTick) {
        this.index = Objects.requireNonNull(index, "index");
        this.cache = Objects.requireNonNull(cache, "cache");
        this.refresher = Objects.requireNonNull(refresher, "refresher");
        this.barkSink = Objects.requireNonNull(barkSink, "barkSink");
        this.sessions = Objects.requireNonNull(sessions, "sessions");
        if (radius <= 0) {
            throw new IllegalArgumentException("radius must be positive");
        }
        this.radiusSquared = radius * radius;
        this.fallbackCooldown = requirePositive(fallbackCooldown, "fallbackCooldown");
        if (maxPlayersPerTick <= 0) {
            throw new IllegalArgumentException("maxPlayersPerTick must be positive");
        }
        this.maxPlayersPerTick = maxPlayersPerTick;
    }

    public ScanStats tick(List<QuestPlayerPosition> onlinePlayers, Instant now) {
        Objects.requireNonNull(now, "now");
        List<QuestPlayerPosition> players = List.copyOf(onlinePlayers);
        validateSessions(players, now);
        if (players.isEmpty()) {
            playerCursor = 0;
            insideNpcIdsByPlayer.clear();
            return new ScanStats(0, 0);
        }

        int processed = Math.min(maxPlayersPerTick, players.size());
        int candidateChecks = 0;
        for (int offset = 0; offset < processed; offset++) {
            QuestPlayerPosition player = players.get((playerCursor + offset) % players.size());
            List<QuestNpcPosition> candidates = index.nearby(player.worldId(), player.chunkX(), player.chunkZ());
            candidateChecks += candidates.size();
            scanPlayer(player, candidates, now);
        }
        playerCursor = (playerCursor + processed) % players.size();
        pruneOffline(players);
        return new ScanStats(processed, candidateChecks);
    }

    private void scanPlayer(
            QuestPlayerPosition player,
            List<QuestNpcPosition> candidates,
            Instant now) {
        Set<UUID> previous = insideNpcIdsByPlayer.getOrDefault(player.playerId(), Set.of());
        Set<UUID> current = new HashSet<>();
        List<QuestNpcPosition> entered = new ArrayList<>();
        for (QuestNpcPosition npc : candidates) {
            if (!npc.worldId().equals(player.worldId()) || distanceSquared(player, npc) > radiusSquared) {
                continue;
            }
            current.add(npc.npcId());
            if (!previous.contains(npc.npcId())) {
                entered.add(npc);
            }
        }
        if (current.isEmpty()) {
            insideNpcIdsByPlayer.remove(player.playerId());
        } else {
            insideNpcIdsByPlayer.put(player.playerId(), Set.copyOf(current));
        }
        entered.forEach(npc -> onEnter(player, npc, now));
    }

    private void onEnter(QuestPlayerPosition player, QuestNpcPosition npc, Instant now) {
        QuestInteractionCache.Entry entry = cache.findFresh(player.playerId(), npc.providerId(), now).orElse(null);
        if (entry == null) {
            refresher.refresh(player.playerId(), player.accountId(), player.lifeId(), npc.providerId())
                    .whenComplete((state, error) -> {
                        if (error == null
                                && state != null
                                && state.lifeId().equals(player.lifeId())
                                && isInside(player.playerId(), npc.npcId())) {
                            sendBark(player.playerId(), npc, state, now);
                        }
                    });
            return;
        }
        sendBark(player.playerId(), npc, entry.state(), now);
    }

    private void sendBark(UUID playerId, QuestNpcPosition npc, QuestInteractionState state, Instant now) {
        QuestProviderSnapshot provider = state.providers().stream()
                .filter(item -> item.providerId().equals(npc.providerId()))
                .findFirst()
                .orElse(null);
        if (provider == null || provider.proximityBark() == null) {
            return;
        }
        QuestProviderSnapshot.ProximityBarkSnapshot bark = provider.proximityBark();
        CooldownKey key = new CooldownKey(playerId, npc.npcId(), bark.key());
        Instant allowedAt = cooldowns.get(key);
        if (allowedAt != null && now.isBefore(allowedAt)) {
            return;
        }
        Duration cooldown = bark.cooldownSeconds() > 0
                ? Duration.ofSeconds(bark.cooldownSeconds())
                : fallbackCooldown;
        cooldowns.put(key, now.plus(cooldown));
        barkSink.send(playerId, NpcDialogueText.formatSpeakerLine(bark.speaker(), bark.text()));
    }

    private boolean isInside(UUID playerId, UUID npcId) {
        return insideNpcIdsByPlayer.getOrDefault(playerId, Set.of()).contains(npcId);
    }

    private void validateSessions(List<QuestPlayerPosition> players, Instant now) {
        Map<UUID, QuestPlayerPosition> playersById = new HashMap<>();
        players.forEach(player -> playersById.put(player.playerId(), player));
        for (QuestOfferSession session : sessions.sessions()) {
            QuestPlayerPosition player = playersById.get(session.playerId());
            boolean invalid = player == null
                    || !index.contains(session.npcId())
                    || !player.worldId().equals(session.worldId())
                    || distanceSquared(player, session.x(), session.y(), session.z()) > radiusSquared
                    || (session.expiresAt() != null && !now.isBefore(session.expiresAt()));
            if (invalid) {
                sessions.cancel(session.token());
            }
        }
    }

    private void pruneOffline(List<QuestPlayerPosition> players) {
        Set<UUID> online = new HashSet<>();
        players.forEach(player -> online.add(player.playerId()));
        insideNpcIdsByPlayer.keySet().removeIf(playerId -> !online.contains(playerId));
        cooldowns.keySet().removeIf(key -> !online.contains(key.playerId()));
    }

    public void clearPlayer(UUID playerId) {
        insideNpcIdsByPlayer.remove(playerId);
        cooldowns.keySet().removeIf(key -> key.playerId().equals(playerId));
        sessions.clearPlayer(playerId);
    }

    public void clear() {
        insideNpcIdsByPlayer.clear();
        cooldowns.clear();
        sessions.clear();
        playerCursor = 0;
    }

    private static double distanceSquared(QuestPlayerPosition player, QuestNpcPosition npc) {
        return distanceSquared(player, npc.x(), npc.y(), npc.z());
    }

    private static double distanceSquared(QuestPlayerPosition player, double x, double y, double z) {
        double dx = player.x() - x;
        double dy = player.y() - y;
        double dz = player.z() - z;
        return dx * dx + dy * dy + dz * dz;
    }

    private static Duration requirePositive(Duration duration, String name) {
        Objects.requireNonNull(duration, name);
        if (duration.isNegative() || duration.isZero()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return duration;
    }

    @FunctionalInterface
    public interface Refresher {
        CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId);
    }

    @FunctionalInterface
    public interface BarkSink {
        void send(UUID playerId, String text);
    }

    public record ScanStats(int playersProcessed, int candidateChecks) {}

    private record CooldownKey(UUID playerId, UUID npcId, String stateKey) {}
}
