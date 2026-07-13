package com.immortalmc.adapter.quest;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class QuestOfferSessionStore {
    private static final Duration CONFIRMATION_TIMEOUT = Duration.ofSeconds(20);

    private final Map<UUID, QuestOfferSession> sessionsByPlayer = new ConcurrentHashMap<>();

    public QuestOfferSession start(
            UUID playerId,
            UUID npcId,
            String providerId,
            String questId,
            UUID worldId,
            double x,
            double y,
            double z,
            Instant startedAt,
            QuestOfferLabel label) {
        QuestOfferSession session = new QuestOfferSession(
                UUID.randomUUID(),
                playerId,
                npcId,
                providerId,
                questId,
                worldId,
                x,
                y,
                z,
                QuestOfferSession.Phase.PLAYING_OFFER,
                startedAt,
                null,
                null,
                label);
        QuestOfferSession previous = sessionsByPlayer.put(playerId, session);
        if (previous != null) {
            previous.label().remove();
        }
        return session;
    }

    public Optional<QuestOfferSession> find(UUID playerId) {
        return Optional.ofNullable(sessionsByPlayer.get(Objects.requireNonNull(playerId, "playerId")));
    }

    public List<QuestOfferSession> sessions() {
        return List.copyOf(sessionsByPlayer.values());
    }

    public boolean isCurrent(UUID token) {
        return findByToken(token).isPresent();
    }

    public boolean markAwaitingConfirmation(UUID token, Instant playbackFinishedAt) {
        QuestOfferSession current = findByToken(token).orElse(null);
        if (current == null || current.phase() != QuestOfferSession.Phase.PLAYING_OFFER) {
            return false;
        }
        QuestOfferSession updated = new QuestOfferSession(
                current.token(),
                current.playerId(),
                current.npcId(),
                current.providerId(),
                current.questId(),
                current.worldId(),
                current.x(),
                current.y(),
                current.z(),
                QuestOfferSession.Phase.AWAITING_CONFIRMATION,
                current.startedAt(),
                playbackFinishedAt,
                playbackFinishedAt.plus(CONFIRMATION_TIMEOUT),
                current.label());
        if (!sessionsByPlayer.replace(current.playerId(), current, updated)) {
            return false;
        }
        current.label().showAwaitingConfirmation();
        return true;
    }

    public boolean cancel(UUID token) {
        QuestOfferSession current = findByToken(token).orElse(null);
        if (current == null || !sessionsByPlayer.remove(current.playerId(), current)) {
            return false;
        }
        current.label().remove();
        return true;
    }

    public void clearPlayer(UUID playerId) {
        QuestOfferSession session = sessionsByPlayer.remove(playerId);
        if (session != null) {
            session.label().remove();
        }
    }

    public void clear() {
        List<QuestOfferSession> sessions = List.copyOf(sessionsByPlayer.values());
        sessionsByPlayer.clear();
        sessions.forEach(session -> session.label().remove());
    }

    private Optional<QuestOfferSession> findByToken(UUID token) {
        Objects.requireNonNull(token, "token");
        return sessionsByPlayer.values().stream()
                .filter(session -> session.token().equals(token))
                .findFirst();
    }
}
