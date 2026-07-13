package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.dialogue.NpcDialogueAudience;
import com.immortalmc.adapter.dialogue.NpcDialogueDefinition;
import com.immortalmc.adapter.dialogue.NpcDialoguePresenter;
import com.immortalmc.adapter.dialogue.NpcDialogueRegistry;
import com.immortalmc.adapter.dialogue.NpcDialogueScheduler;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.quest.QuestInteractionService;
import com.immortalmc.adapter.quest.QuestOfferLabel;
import com.immortalmc.adapter.quest.QuestOfferLabelPresenter;
import com.immortalmc.adapter.quest.QuestOfferSession;
import com.immortalmc.adapter.quest.QuestOfferSessionStore;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BiConsumer;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

class QuestProviderInteractionActionTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");
    private static final UUID WORLD_ID = UUID.fromString("30000000-0000-0000-0000-000000000001");
    private static final UUID NPC_ID = UUID.fromString("40000000-0000-0000-0000-000000000001");

    @Test
    void firstClickPlaysOfferAndSecondClickAcceptsAuthoritatively() {
        PlayerSessionCache playerSessions = new PlayerSessionCache();
        playerSessions.store(new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Sensen"),
                new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
        FakeQuestService quests = new FakeQuestService();
        RecordingScheduler scheduler = new RecordingScheduler();
        NpcDialogueRegistry dialogues = new NpcDialogueRegistry(() -> Map.of(
                "first-steps.available",
                new NpcDialogueDefinition(
                        "first-steps.available",
                        "初入凡尘",
                        "老村民",
                        List.of("opening"),
                        List.of("offer"),
                        10,
                        "entity.villager.ambient",
                        1.0f)));
        dialogues.reload();
        QuestOfferSessionStore offerSessions = new QuestOfferSessionStore();
        RecordingLabel label = new RecordingLabel();
        AtomicReference<TrackedQuestSnapshot> rendered = new AtomicReference<>();
        QuestProviderInteractionAction action = new QuestProviderInteractionAction(
                playerSessions,
                quests,
                dialogues,
                new NpcDialoguePresenter(scheduler),
                offerSessions,
                (player, npc) -> label,
                (playerId, tracked) -> rendered.set(tracked),
                new RecordingAdapterLogger(),
                ignored -> new RecordingAudience(),
                Clock.fixed(Instant.parse("2026-07-13T12:00:00Z"), ZoneOffset.UTC));
        EntityInteractionDefinition definition = definition();
        BukkitEntityInteractionContext context = new BukkitEntityInteractionContext(player(), npc());

        action.handle(definition, context);

        assertEquals(1, quests.refreshCalls.get());
        assertEquals(0, quests.acceptCalls.get());
        assertEquals(QuestOfferSession.Phase.PLAYING_OFFER, offerSessions.find(PLAYER_ID).orElseThrow().phase());

        scheduler.runAll();
        assertEquals(QuestOfferSession.Phase.AWAITING_CONFIRMATION, offerSessions.find(PLAYER_ID).orElseThrow().phase());
        assertEquals(1, label.awaiting.get());

        action.handle(definition, context);

        assertEquals(1, quests.acceptCalls.get());
        assertTrue(offerSessions.find(PLAYER_ID).isEmpty());
        assertEquals(1, label.removals.get());
        assertEquals("first-steps", rendered.get().questId());
    }

    private static EntityInteractionDefinition definition() {
        return new EntityInteractionDefinition(
                "old-man-quests",
                QuestProviderInteractionAction.ACTION,
                new EntityBinding("world", NPC_ID),
                "PLAYER",
                true,
                false,
                Map.of(
                        QuestProviderInteractionAction.PROVIDER_ID_KEY, "old-man",
                        QuestProviderInteractionAction.CITIZENS_NPC_UUID_KEY, NPC_ID.toString()));
    }

    private static Player player() {
        return proxy(Player.class, Map.of("getUniqueId", PLAYER_ID));
    }

    private static Entity npc() {
        World world = proxy(World.class, Map.of("getUID", WORLD_ID, "getName", "world"));
        return proxy(
                Entity.class,
                Map.of(
                        "getUniqueId", NPC_ID,
                        "getWorld", world,
                        "getLocation", new Location(world, 1, 2, 3)));
    }

    @SuppressWarnings("unchecked")
    private static <T> T proxy(Class<T> type, Map<String, Object> returns) {
        return (T) Proxy.newProxyInstance(
                type.getClassLoader(),
                new Class<?>[] {type},
                (proxy, method, args) -> returns.containsKey(method.getName())
                        ? returns.get(method.getName())
                        : defaultValue(method.getReturnType()));
    }

    private static Object defaultValue(Class<?> type) {
        if (!type.isPrimitive()) {
            return null;
        }
        if (type == boolean.class) {
            return false;
        }
        return 0;
    }

    private static final class FakeQuestService implements QuestInteractionService {
        private final AtomicInteger refreshCalls = new AtomicInteger();
        private final AtomicInteger acceptCalls = new AtomicInteger();

        @Override
        public CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId) {
            refreshCalls.incrementAndGet();
            return CompletableFuture.completedFuture(state("available", null));
        }

        @Override
        public CompletableFuture<QuestMutationResult> accept(
                UUID playerId,
                UUID accountId,
                UUID lifeId,
                String questId,
                String providerId,
                UUID operationId) {
            acceptCalls.incrementAndGet();
            QuestInteractionState state = state(
                    "active",
                    new TrackedQuestSnapshot("first-steps", "初入凡尘", "active", List.of(), "前往鉴灵师处"));
            return CompletableFuture.completedFuture(
                    new QuestMutationResult(operationId, true, state.providers().getFirst().quests().getFirst(), state));
        }

        @Override
        public CompletableFuture<QuestMutationResult> turnIn(
                UUID playerId,
                UUID accountId,
                UUID lifeId,
                String questId,
                String providerId,
                UUID operationId) {
            throw new UnsupportedOperationException();
        }

        private static QuestInteractionState state(String questState, TrackedQuestSnapshot tracked) {
            String action = questState.equals("available") ? "offer" : "remind";
            ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                    "first-steps",
                    "初入凡尘",
                    "main",
                    questState,
                    action,
                    "first-steps.available",
                    List.of());
            QuestProviderSnapshot provider = new QuestProviderSnapshot(
                    "old-man",
                    "first-steps:" + questState,
                    List.of(quest),
                    List.of("first-steps"),
                    "first-steps",
                    null);
            return new QuestInteractionState(
                    1,
                    ACCOUNT_ID,
                    LIFE_ID,
                    new QuestRevisionVector(1, questState.equals("available") ? 0 : 1, "sha256:definitions"),
                    List.of(provider),
                    tracked,
                    2000);
        }
    }

    private static final class RecordingScheduler implements NpcDialogueScheduler {
        private final List<Runnable> tasks = new ArrayList<>();

        @Override
        public void runLater(int delayTicks, Runnable task) {
            tasks.add(task);
        }

        void runAll() {
            List.copyOf(tasks).forEach(Runnable::run);
        }
    }

    private static final class RecordingLabel implements QuestOfferLabel {
        private final AtomicInteger awaiting = new AtomicInteger();
        private final AtomicInteger removals = new AtomicInteger();

        @Override
        public void showAwaitingConfirmation() {
            awaiting.incrementAndGet();
        }

        @Override
        public void remove() {
            removals.incrementAndGet();
        }
    }

    private static final class RecordingAudience implements NpcDialogueAudience {
        @Override
        public void sendMessage(String message) {}

        @Override
        public void playSound(String sound, float volume, float pitch) {}
    }
}
