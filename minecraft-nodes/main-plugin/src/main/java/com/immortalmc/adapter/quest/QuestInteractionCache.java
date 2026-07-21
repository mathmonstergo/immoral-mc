package com.immortalmc.adapter.quest;

import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestRevisionVector;
import java.time.Duration;
import java.time.Instant;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;

public final class QuestInteractionCache {
    public static final Duration DEFAULT_TTL = Duration.ofSeconds(2);

    private final Duration ttl;
    private final AtomicLong generationSequence = new AtomicLong();
    private final Map<Key, Generation> currentGenerations = new HashMap<>();
    private final Map<Key, Entry> entries = new HashMap<>();

    public QuestInteractionCache() {
        this(DEFAULT_TTL);
    }

    public QuestInteractionCache(Duration ttl) {
        this.ttl = Objects.requireNonNull(ttl, "ttl");
        if (ttl.isNegative() || ttl.isZero()) {
            throw new IllegalArgumentException("ttl must be positive");
        }
    }

    public synchronized Generation nextGeneration(UUID playerId, String providerId, UUID expectedLifeId) {
        Key key = new Key(playerId, providerId);
        Objects.requireNonNull(expectedLifeId, "expectedLifeId");
        Generation current = currentGenerations.get(key);
        if (current != null && !current.expectedLifeId().equals(expectedLifeId)) {
            entries.remove(key);
        }
        Generation generation = new Generation(generationSequence.incrementAndGet(), expectedLifeId);
        currentGenerations.put(key, generation);
        return generation;
    }

    public synchronized boolean publish(
            UUID playerId,
            String providerId,
            Generation generation,
            QuestInteractionState state,
            Instant fetchedAt) {
        Key key = new Key(playerId, providerId);
        Objects.requireNonNull(state, "state");
        Objects.requireNonNull(fetchedAt, "fetchedAt");
        Generation currentGeneration = currentGenerations.get(key);
        if (!generation.equals(currentGeneration)
                || !state.lifeId().equals(generation.expectedLifeId())
                || !containsProvider(state, providerId)) {
            return false;
        }

        Entry current = entries.get(key);
        if (current != null && current.state().lifeId().equals(state.lifeId())
                && isRevisionOlder(state.revision(), current.state().revision())) {
            return false;
        }
        entries.put(key, new Entry(state, fetchedAt, generation));
        return true;
    }

    public synchronized Optional<Entry> findFresh(UUID playerId, String providerId, Instant now) {
        Objects.requireNonNull(now, "now");
        return findLastConfirmed(playerId, providerId)
                .filter(entry -> now.isBefore(entry.fetchedAt().plus(ttl)));
    }

    public synchronized Optional<Entry> findLastConfirmed(UUID playerId, String providerId) {
        Key key = new Key(playerId, providerId);
        Entry entry = entries.get(key);
        Generation current = currentGenerations.get(key);
        if (entry == null || current == null || !entry.state().lifeId().equals(current.expectedLifeId())) {
            return Optional.empty();
        }
        return Optional.of(entry);
    }

    public synchronized void invalidateSuperseded(
            UUID playerId, QuestInteractionState authoritativeState) {
        Objects.requireNonNull(playerId, "playerId");
        Objects.requireNonNull(authoritativeState, "authoritativeState");
        Set<Key> invalidatedKeys = new HashSet<>();
        currentGenerations.keySet().stream()
                .filter(key -> key.playerId().equals(playerId))
                .filter(key -> {
                    Entry entry = entries.get(key);
                    return entry == null || isSuperseded(entry.state(), authoritativeState);
                })
                .forEach(invalidatedKeys::add);
        invalidatedKeys.forEach(entries::remove);
        invalidatedKeys.forEach(currentGenerations::remove);
    }

    public synchronized void clearPlayer(UUID playerId) {
        Objects.requireNonNull(playerId, "playerId");
        entries.keySet().removeIf(key -> key.playerId().equals(playerId));
        currentGenerations.keySet().removeIf(key -> key.playerId().equals(playerId));
    }

    public synchronized void clear() {
        entries.clear();
        currentGenerations.clear();
    }

    private static boolean containsProvider(QuestInteractionState state, String providerId) {
        return state.providers().stream().anyMatch(provider -> provider.providerId().equals(providerId));
    }

    private static boolean isRevisionOlder(QuestRevisionVector candidate, QuestRevisionVector current) {
        return candidate.isOlderThan(current);
    }

    private static boolean isSuperseded(
            QuestInteractionState cached, QuestInteractionState authoritative) {
        return !cached.accountId().equals(authoritative.accountId())
                || !cached.lifeId().equals(authoritative.lifeId())
                || cached.revision().isSupersededBy(authoritative.revision());
    }

    public record Entry(QuestInteractionState state, Instant fetchedAt, Generation generation) {
        public Entry {
            Objects.requireNonNull(state, "state");
            Objects.requireNonNull(fetchedAt, "fetchedAt");
        }
    }

    public record Generation(long value, UUID expectedLifeId) {
        public Generation {
            Objects.requireNonNull(expectedLifeId, "expectedLifeId");
        }
    }

    private record Key(UUID playerId, String providerId) {
        private Key {
            Objects.requireNonNull(playerId, "playerId");
            Objects.requireNonNull(providerId, "providerId");
        }
    }
}
