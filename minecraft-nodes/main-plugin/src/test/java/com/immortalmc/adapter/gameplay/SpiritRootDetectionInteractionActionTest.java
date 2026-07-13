package com.immortalmc.adapter.gameplay;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.client.ProviderQuestSnapshot;
import com.immortalmc.adapter.client.QuestInteractionState;
import com.immortalmc.adapter.client.QuestMutationResult;
import com.immortalmc.adapter.client.QuestProviderSnapshot;
import com.immortalmc.adapter.client.QuestRevisionVector;
import com.immortalmc.adapter.client.SpiritRootDetectionResult;
import com.immortalmc.adapter.client.SpiritRootSnapshot;
import com.immortalmc.adapter.client.TrackedQuestSnapshot;
import com.immortalmc.adapter.command.SpiritRootCommandMessages;
import com.immortalmc.adapter.content.EntityBinding;
import com.immortalmc.adapter.content.EntityInteractionDefinition;
import com.immortalmc.adapter.interaction.BukkitEntityInteractionContext;
import com.immortalmc.adapter.presentation.SpiritRootParticlePresenter;
import com.immortalmc.adapter.presentation.SpiritRootTitlePresenter;
import com.immortalmc.adapter.quest.QuestInteractionService;
import com.immortalmc.adapter.session.PlayerSessionCache;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

class SpiritRootDetectionInteractionActionTest {
    private static final UUID PLAYER_ID = UUID.fromString("00000000-0000-0000-0000-000000000010");
    private static final UUID ACCOUNT_ID = UUID.fromString("10000000-0000-0000-0000-000000000001");
    private static final UUID LIFE_ID = UUID.fromString("20000000-0000-0000-0000-000000000001");

    @Test
    void successfulDetectionShowsTitleParticlesAndRefreshesQuestOnce() {
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Sensen"),
                new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
        SpiritRootSnapshot root = new SpiritRootSnapshot("variant", "异灵根", List.of("金"), "金雷", "雷");
        SpiritRootDetectionUseCase useCase = new SpiritRootDetectionUseCase(
                accountId -> CompletableFuture.completedFuture(new SpiritRootDetectionResult(LIFE_ID, root, false)),
                sessions,
                new SpiritRootCommandMessages(),
                new RecordingAdapterLogger(),
                Runnable::run);
        AtomicInteger particles = new AtomicInteger();
        AtomicInteger titles = new AtomicInteger();
        FakeQuestService quests = new FakeQuestService();
        AtomicReference<TrackedQuestSnapshot> rendered = new AtomicReference<>();
        SpiritRootDetectionInteractionAction action = new SpiritRootDetectionInteractionAction(
                useCase,
                (player, entity, spiritRoot) -> particles.incrementAndGet(),
                (player, spiritRoot) -> titles.incrementAndGet(),
                sessions,
                quests,
                (playerId, tracked) -> rendered.set(tracked));
        EntityInteractionDefinition definition = new EntityInteractionDefinition(
                "detector",
                SpiritRootDetectionInteractionAction.ACTION,
                new EntityBinding("world", UUID.fromString("40000000-0000-0000-0000-000000000001")),
                "PLAYER",
                true,
                false,
                Map.of(SpiritRootDetectionInteractionAction.QUEST_PROVIDER_ID_KEY, "old-man"));

        action.handle(definition, new BukkitEntityInteractionContext(player(), entity()));

        assertEquals(1, particles.get());
        assertEquals(1, titles.get());
        assertEquals(1, quests.refreshes.get());
        assertEquals("first-steps", rendered.get().questId());
    }

    private static Player player() {
        return proxy(Player.class, Map.of("getUniqueId", PLAYER_ID));
    }

    private static Entity entity() {
        return proxy(Entity.class, Map.of());
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
        private final AtomicInteger refreshes = new AtomicInteger();

        @Override
        public CompletableFuture<QuestInteractionState> refresh(
                UUID playerId, UUID accountId, UUID lifeId, String providerId) {
            refreshes.incrementAndGet();
            TrackedQuestSnapshot tracked = new TrackedQuestSnapshot(
                    "first-steps", "初入凡尘", "ready_to_turn_in", List.of(), "返回老村民处");
            ProviderQuestSnapshot quest = new ProviderQuestSnapshot(
                    "first-steps", "初入凡尘", "main", "ready_to_turn_in", "turn_in", null, List.of());
            QuestProviderSnapshot provider = new QuestProviderSnapshot(
                    providerId, "first-steps:ready_to_turn_in", List.of(quest), List.of("first-steps"), "first-steps", null);
            return CompletableFuture.completedFuture(new QuestInteractionState(
                    1,
                    accountId,
                    lifeId,
                    new QuestRevisionVector(2, 1, "sha256:definitions"),
                    List.of(provider),
                    tracked,
                    2000));
        }

        @Override
        public CompletableFuture<QuestMutationResult> accept(
                UUID playerId, UUID accountId, UUID lifeId, String questId, String providerId, UUID operationId) {
            throw new UnsupportedOperationException();
        }

        @Override
        public CompletableFuture<QuestMutationResult> turnIn(
                UUID playerId, UUID accountId, UUID lifeId, String questId, String providerId, UUID operationId) {
            throw new UnsupportedOperationException();
        }
    }
}
