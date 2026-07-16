package com.immortalmc.adapter.presentation;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.destroystokyo.paper.event.entity.ExperienceOrbMergeEvent;
import com.destroystokyo.paper.event.player.PlayerPickupExperienceEvent;
import com.immortalmc.adapter.client.CombatKillEventRequest;
import com.immortalmc.adapter.client.CombatKillResult;
import com.immortalmc.adapter.testsupport.RecordingAdapterLogger;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicInteger;
import org.bukkit.NamespacedKey;
import org.bukkit.entity.ExperienceOrb;
import org.bukkit.entity.Player;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.junit.jupiter.api.Test;

class BukkitCultivationRewardPresenterTest {
    private static final UUID OWNER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID OTHER_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final NamespacedKey OWNER_KEY = new NamespacedKey("immortalmc", "cultivation_orb_owner");

    @Test
    void acceptedRewardSpawnsBoundZeroXpOrbsUsingOnlyMobLevelForCount() {
        Player owner = mock(Player.class);
        List<ExperienceOrb> spawned = new ArrayList<>();
        BukkitCultivationRewardPresenter presenter = presenter(owner, spawned, ignored -> {});

        presenter.present(request("25"), acceptedResult(999_999L, 0L));

        assertEquals(3, spawned.size());
        for (ExperienceOrb orb : spawned) {
            verify(orb).setExperience(0);
            verify(orb).setCount(1);
            verify(orb.getPersistentDataContainer())
                    .set(OWNER_KEY, PersistentDataType.STRING, OWNER_ID.toString());
        }
    }

    @Test
    void duplicateAndOfflineOwnerNeverSpawnPresentation() {
        AtomicInteger spawns = new AtomicInteger();
        BukkitCultivationRewardPresenter presenter = new BukkitCultivationRewardPresenter(
                OWNER_KEY,
                ignored -> null,
                (world, x, y, z) -> {
                    spawns.incrementAndGet();
                    return orb();
                },
                ignored -> {},
                new RecordingAdapterLogger());

        presenter.present(request("100"), duplicateResult());
        presenter.present(request("100"), acceptedResult(10L, 10L));

        assertEquals(0, spawns.get());
    }

    @Test
    void pickupIsOwnerBoundRemovesZeroXpOrbAndUpdatesOnlyOwnerAnimation() {
        List<UUID> pickups = new ArrayList<>();
        BukkitCultivationRewardPresenter presenter = presenter(mock(Player.class), new ArrayList<>(), pickups::add);
        ExperienceOrb orb = taggedOrb(OWNER_ID);
        PlayerPickupExperienceEvent wrongOwner = mock(PlayerPickupExperienceEvent.class);
        Player other = mock(Player.class);
        when(other.getUniqueId()).thenReturn(OTHER_ID);
        when(wrongOwner.getPlayer()).thenReturn(other);
        when(wrongOwner.getExperienceOrb()).thenReturn(orb);

        presenter.onPickup(wrongOwner);

        verify(wrongOwner).setCancelled(true);
        verify(orb, never()).remove();
        assertTrue(pickups.isEmpty());

        PlayerPickupExperienceEvent ownerPickup = mock(PlayerPickupExperienceEvent.class);
        Player owner = mock(Player.class);
        when(owner.getUniqueId()).thenReturn(OWNER_ID);
        when(ownerPickup.getPlayer()).thenReturn(owner);
        when(ownerPickup.getExperienceOrb()).thenReturn(orb);

        presenter.onPickup(ownerPickup);

        verify(ownerPickup).setCancelled(true);
        verify(orb).setExperience(0);
        verify(orb).remove();
        assertEquals(List.of(OWNER_ID), pickups);
    }

    @Test
    void taggedRewardOrbsCannotMergeWithVanillaOrOtherOwnerOrbs() {
        BukkitCultivationRewardPresenter presenter = presenter(mock(Player.class), new ArrayList<>(), ignored -> {});
        ExperienceOrbMergeEvent event = mock(ExperienceOrbMergeEvent.class);
        ExperienceOrb source = taggedOrb(OWNER_ID);
        ExperienceOrb target = orb();
        when(event.getMergeSource()).thenReturn(source);
        when(event.getMergeTarget()).thenReturn(target);

        presenter.onMerge(event);

        verify(event).setCancelled(true);
    }

    private static BukkitCultivationRewardPresenter presenter(
            Player owner,
            List<ExperienceOrb> spawned,
            java.util.function.Consumer<UUID> onPickup) {
        when(owner.getUniqueId()).thenReturn(OWNER_ID);
        return new BukkitCultivationRewardPresenter(
                OWNER_KEY,
                playerId -> playerId.equals(OWNER_ID) ? owner : null,
                (world, x, y, z) -> {
                    ExperienceOrb orb = orb();
                    spawned.add(orb);
                    return orb;
                },
                onPickup,
                new RecordingAdapterLogger());
    }

    private static ExperienceOrb orb() {
        ExperienceOrb orb = mock(ExperienceOrb.class);
        when(orb.getPersistentDataContainer()).thenReturn(mock(PersistentDataContainer.class));
        return orb;
    }

    private static ExperienceOrb taggedOrb(UUID ownerId) {
        ExperienceOrb orb = orb();
        when(orb.getPersistentDataContainer().get(OWNER_KEY, PersistentDataType.STRING))
                .thenReturn(ownerId.toString());
        when(orb.getPersistentDataContainer().has(OWNER_KEY, PersistentDataType.STRING))
                .thenReturn(true);
        return orb;
    }

    private static CombatKillEventRequest request(String mobLevel) {
        return new CombatKillEventRequest(
                1,
                UUID.fromString("33333333-3333-4333-8333-333333333333"),
                "main-1",
                UUID.fromString("44444444-4444-4444-8444-444444444444"),
                "AzureWolf",
                mobLevel,
                OWNER_ID,
                UUID.fromString("55555555-5555-4555-8555-555555555555"),
                "direct",
                null,
                null,
                "minecraft:overworld",
                12.5,
                64.0,
                -8.25,
                "2026-07-16T12:00:00Z");
    }

    private static CombatKillResult acceptedResult(long configured, long credited) {
        return new CombatKillResult(
                request("1").eventId(),
                "accepted",
                UUID.fromString("66666666-6666-4666-8666-666666666666"),
                request("1").sourceLifeId(),
                configured,
                credited,
                credited);
    }

    private static CombatKillResult duplicateResult() {
        return new CombatKillResult(
                request("1").eventId(),
                "duplicate",
                UUID.fromString("66666666-6666-4666-8666-666666666666"),
                request("1").sourceLifeId(),
                10L,
                10L,
                10L);
    }
}
