package com.immortalmc.adapter.combat;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.immortalmc.adapter.client.AccountSnapshot;
import com.immortalmc.adapter.client.LifeSnapshot;
import com.immortalmc.adapter.client.PlayerLoginResult;
import com.immortalmc.adapter.session.PlayerSessionCache;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityRemoveEvent;
import org.junit.jupiter.api.Test;

class BukkitCombatAttributionListenerTest {
    private static final UUID PLAYER_ID =
            UUID.fromString("11111111-1111-4111-8111-111111111111");
    private static final UUID ACCOUNT_ID =
            UUID.fromString("22222222-2222-4222-8222-222222222222");
    private static final UUID LIFE_ID =
            UUID.fromString("33333333-3333-4333-8333-333333333333");
    private static final UUID TARGET_ID =
            UUID.fromString("44444444-4444-4444-8444-444444444444");
    private static final Instant NOW = Instant.parse("2026-07-15T12:00:00Z");

    @Test
    void recordsLethalDirectPlayerDamageWithTheCurrentLife() {
        Fixture fixture = fixture();
        Player player = player();
        EntityDamageByEntityEvent event = damageEvent(player, false, 10.0, 10.0);

        fixture.listener().onDamage(event);

        CombatSource source = fixture.tracker().consumeLethal(TARGET_ID, NOW).orElseThrow().source();
        assertEquals(CombatAttributionKind.DIRECT, source.kind());
        assertEquals(PLAYER_ID, source.playerUuid());
        assertEquals(LIFE_ID, source.sourceLifeId());
        assertTrue(source.techniqueId() == null);
        assertTrue(source.castId() == null);
    }

    @Test
    void recordsLethalProjectileDamageForItsPlayerShooter() {
        Fixture fixture = fixture();
        Projectile projectile = mock(Projectile.class);
        Player shooter = player();
        when(projectile.getShooter()).thenReturn(shooter);
        EntityDamageByEntityEvent event = damageEvent(projectile, false, 12.0, 10.0);

        fixture.listener().onDamage(event);

        CombatSource source = fixture.tracker().consumeLethal(TARGET_ID, NOW).orElseThrow().source();
        assertEquals(CombatAttributionKind.PROJECTILE, source.kind());
        assertEquals(PLAYER_ID, source.playerUuid());
        assertEquals(LIFE_ID, source.sourceLifeId());
    }

    @Test
    void treatsFinalDamageAsAlreadyReducedByAbsorption() {
        Fixture fixture = fixture();
        EntityDamageByEntityEvent event = damageEvent(player(), false, 10.0, 10.0, 5.0);

        fixture.listener().onDamage(event);

        assertTrue(fixture.tracker().consumeLethal(TARGET_ID, NOW).isPresent());
    }

    @Test
    void ignoresCancelledNonlethalAndAnonymousDamage() {
        Fixture fixture = fixture();
        fixture.listener().onDamage(damageEvent(player(), true, 20.0, 10.0));
        fixture.listener().onDamage(damageEvent(player(), false, 9.0, 10.0));
        Projectile anonymous = mock(Projectile.class);
        fixture.listener().onDamage(damageEvent(anonymous, false, 20.0, 10.0));

        assertTrue(fixture.tracker().consumeLethal(TARGET_ID, NOW).isEmpty());
    }

    @Test
    void clearsAttributionWhenTheTargetLeavesTheWorld() {
        Fixture fixture = fixture();
        fixture.listener().onDamage(damageEvent(player(), false, 10.0, 10.0));
        EntityRemoveEvent removal = mock(EntityRemoveEvent.class);
        LivingEntity target = livingTarget(10.0);
        when(removal.getEntity()).thenReturn(target);

        fixture.listener().onEntityRemoved(removal);

        assertTrue(fixture.tracker().consumeLethal(TARGET_ID, NOW).isEmpty());
    }

    private static Fixture fixture() {
        CombatAttributionTracker tracker =
                new CombatAttributionTracker(Duration.ofMinutes(15), 100);
        PlayerSessionCache sessions = new PlayerSessionCache();
        sessions.store(new PlayerLoginResult(
                new AccountSnapshot(ACCOUNT_ID, PLAYER_ID, "Combatant"),
                new LifeSnapshot(LIFE_ID, ACCOUNT_ID, 1, "alive", null)));
        BukkitCombatAttributionListener listener = new BukkitCombatAttributionListener(
                tracker,
                sessions,
                Clock.fixed(NOW, ZoneOffset.UTC),
                Duration.ofMinutes(15));
        return new Fixture(tracker, listener);
    }

    private static Player player() {
        Player player = mock(Player.class);
        when(player.getUniqueId()).thenReturn(PLAYER_ID);
        return player;
    }

    private static EntityDamageByEntityEvent damageEvent(
            org.bukkit.entity.Entity damager,
            boolean cancelled,
            double finalDamage,
            double health) {
        return damageEvent(damager, cancelled, finalDamage, health, 0.0);
    }

    private static EntityDamageByEntityEvent damageEvent(
            org.bukkit.entity.Entity damager,
            boolean cancelled,
            double finalDamage,
            double health,
            double absorption) {
        EntityDamageByEntityEvent event = mock(EntityDamageByEntityEvent.class);
        LivingEntity target = livingTarget(health, absorption);
        when(event.isCancelled()).thenReturn(cancelled);
        when(event.getDamager()).thenReturn(damager);
        when(event.getEntity()).thenReturn(target);
        when(event.getFinalDamage()).thenReturn(finalDamage);
        return event;
    }

    private static LivingEntity livingTarget(double health) {
        return livingTarget(health, 0.0);
    }

    private static LivingEntity livingTarget(double health, double absorption) {
        LivingEntity target = mock(LivingEntity.class);
        when(target.getUniqueId()).thenReturn(TARGET_ID);
        when(target.getHealth()).thenReturn(health);
        when(target.getAbsorptionAmount()).thenReturn(absorption);
        return target;
    }

    private record Fixture(
            CombatAttributionTracker tracker,
            BukkitCombatAttributionListener listener) {}
}
