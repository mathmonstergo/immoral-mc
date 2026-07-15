# MythicMobs API research for kill rewards

Research date: 2026-07-15

## Official sources

* MythicMobs API wiki:
  <https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API>
* Same wiki page through the public GitLab API (used to read the current raw
  content): <https://git.mythiccraft.io/api/v4/projects/20/wikis/API>
* Official JavaDocs:
  <https://www.mythiccraft.io/javadocs/mythic/>
* Official Maven repository:
  <https://mvn.lumine.io/repository/maven-public/>
* Maven metadata for the official distribution artifact:
  <https://mvn.lumine.io/repository/maven-public/io/lumine/Mythic-Dist/maven-metadata.xml>

The official API page currently specifies:

```kotlin
repositories {
    maven(url = "https://mvn.lumine.io/repository/maven-public/")
}

dependencies {
    compileOnly("io.lumine:Mythic-Dist:5.12.1")
}
```

It also explicitly permits declaring MythicMobs as either `depend` or
`softdepend` in `plugin.yml`.

## Verified 5.12.1 death event contract

The official JavaDocs expose `io.lumine.mythic.bukkit.events.MythicMobDeathEvent`.
The current `Mythic-Dist-5.12.1.jar` was downloaded from the official Maven
repository and inspected with `javap`. Its relevant public API is:

```java
public final class MythicMobDeathEvent extends Event {
    ActiveMob getMob();
    Entity getEntity();
    MythicMob getMobType();
    double getMobLevel();
    LivingEntity getKiller();
    List<ItemStack> getDrops();
    void setDrops(List<ItemStack> drops);
}
```

`MythicMob#getInternalName()` supplies the stable content ID used by Mythic
configuration. `ActiveMob#getUniqueId()` and `event.getEntity().getUniqueId()`
expose the spawned mob entity UUID. The event is a normal, non-cancellable
Bukkit event and the constructor does not enforce a non-null killer.

## Recommended integration

Use `MythicMobDeathEvent` directly. On the Paper main thread, copy only these
immutable facts into an Adapter-owned request object:

* configured ImmortalMC `server_id`;
* dead entity UUID;
* `event.getMobType().getInternalName()`;
* Mythic mob level;
* player/source identity from ImmortalMC's consumed lethal attribution record;
* world/position and occurred-at timestamp as non-authoritative audit facts.

Then release all Bukkit/Mythic object references and send the HTTP request
asynchronously. Do not access Bukkit or Mythic objects from the HTTP callback.
`MythicMobDeathEvent#getKiller()` is deliberately not used to reconstruct a
missing source. Ordinary player melee/projectile damage is recorded earlier by
the Bukkit attribution listener, while custom delayed effects must preserve an
explicit `CombatSource`; missing attribution produces no reward event.

The stable source event identity should be derived from the configured server
ID plus the dead Mythic entity UUID. A new random UUID generated for every HTTP
attempt would break retry deduplication. The Game Service ledger should be
unique per `(source_type, source_event_id, recipient_life_id)`, allowing a later
party-sharing rule to create multiple recipient entries for one kill.

## Optional dependency boundary

Use `softdepend: [Citizens, MythicMobs]` because ImmortalMC core login/quest
behavior must still start without MythicMobs. Keep all Mythic-linked classes in
a dedicated integration package/loader and register the death listener only
after the plugin manager confirms MythicMobs is enabled. This mirrors the
project's optional Citizens boundary and reduces accidental class loading when
MythicMobs is absent.

Compile against the pinned official `Mythic-Dist:5.12.1` artifact and do not
shade it into the ImmortalMC jar. A missing integration is an explicit logged
state. A present but binary-incompatible MythicMobs version must fail visibly
during integration enablement/test-server boot; it must not silently fall back
to generic entity matching.

## Rejected alternatives

### Generic `EntityDeathEvent` plus name/PDC/config heuristics

Rejected. It duplicates MythicMobs entity classification and can misidentify
vanilla or disguised entities. MythicMobs already emits a typed death event.

### Generic death event plus `MythicBukkit` manager lookup

Supported by the official API for cases where only a Bukkit entity is
available, but unnecessary here. `MythicMobDeathEvent` already contains the
`ActiveMob`, typed mob definition, level, entity, and killer.

### A custom Mythic mechanic on every mob's `~onDeath`

Rejected for the core reward pipeline. It requires content authors to remember
the mechanic on every rewardable mob, makes missed configuration look like lost
progression, and can duplicate delivery when combined with event listeners.
Custom mechanics remain appropriate for presentation/content behavior, not for
the universal authoritative reward ingestion boundary.

## What MythicMobs does not provide for this slice

MythicMobs provides the typed death fact, mob identity, mob level, entity, and
killer. It does not provide our Game Service idempotency ledger, current-life
resolution, unrefined-cultivation balance, or reliable cross-process HTTP
delivery. Those are ImmortalMC responsibilities rather than duplicated
MythicMobs features.

The unresolved reliability choice is whether the first version persists a
small Adapter outbox for pending kill facts. Without one, an event is lost if
the Game Service is unavailable after the death event fires.
