# ImmortalMC plugin integration recommendation

Research date: 2026-07-13

## Decision summary

Adopt a hybrid stack with strict ownership boundaries:

| Area | Owner | Decision |
|---|---|---|
| NPC entity, skin, name, navigation, lifecycle | Citizens | Adopt now through an optional adapter |
| Dialogue, quest definitions, progress, conditions, rewards | ImmortalMC + Game Service | Keep custom and authoritative |
| Mob templates, spawning, AI, threat, skills, VFX | MythicMobs | Adopt incrementally through an optional adapter |
| Combat result, loot eligibility, progression rewards | Game Service | Keep authoritative |
| Traditional classes, levels, mana, professions, built-in quests | MMOCore | Reject as ImmortalMC authority |
| MMOCore waypoint/skill-binding/UI capabilities | Isolated PoC only | Defer until a specific proven gap exists |

Citizens and MythicMobs fit the architecture because they can provide
Minecraft mechanisms while emitting facts through stable APIs/events. MMOCore
is different: its central abstraction is a persistent `PlayerData` aggregate
that owns nearly every RPG subsystem, creating a second authority beside Game
Service.

## Citizens integration contract

### Identity

Persist `NPC#getUniqueId()` as the external NPC identity:

```yaml
target:
  provider: citizens
  npc-uuid: 00000000-0000-0000-0000-000000000000
```

Do not persist `NPC#getId()` as a domain key and do not treat the spawned
Bukkit entity UUID as the durable identity. Player NPCs can expose a modified
Minecraft UUID and every NPC can despawn/respawn while retaining its Citizens
UUID.

### Events and routing

* Route interaction from `NPCRightClickEvent` into the existing ImmortalMC
  action router.
* When Citizens integration is active, the generic
  `PlayerInteractEntityEvent` listener must skip Citizens entities to prevent
  duplicate dialogue starts.
* `NPCDespawnEvent` retains the binding; `NPCRemoveEvent` invalidates or removes
  it; `NPCSpawnEvent` refreshes runtime caches only.
* Add a per-player conversation guard so rapid repeated clicks cannot start
  overlapping sessions.

### Dependency and failure behavior

* Use pinned `compileOnly` Citizens API/main dependency; do not shade Citizens.
* Declare `softdepend: [Citizens]` and isolate Citizens-referencing classes so
  ImmortalMC still loads when Citizens is absent.
* Reconcile bindings after `CitizensEnableEvent`.
* Keep Citizens `TargetCitizensNPCs: false` in MythicMobs by default.

## MythicMobs integration contract

### Identity

* Map the Mythic internal mob name to the Game Service `mob_template_id`.
* Use the ActiveMob/Bukkit UUID as the runtime mob instance ID.
* Never persist a numeric Bukkit entity ID or display name as the business key.

### First vertical slice

Start with one mob and prove this chain before authoritative real-time damage:

```text
Mythic spawn -> Adapter records template/instance
player kills mob -> Adapter captures one death fact
Game Service idempotently resolves reward
Adapter presents/delivers committed result
```

Use stable `death_event_id`/encounter IDs so retries cannot duplicate quest
progress or rewards.

### Drops and damage

* Clear Mythic death drops, Mythic loot drops, Bukkit drops, experience, and
  money before issuing Game Service-authorized rewards. Verify all three event
  layers because Mythic and vanilla paths can coexist.
* Never block the Paper/entity thread on HTTP.
* Authoritative damage needs an action ID, cancellation or suppression of the
  original local result, an async Game Service request, an entity-alive/world
  recheck, and application back on the entity-owning thread.
* Use a re-entry marker so applying approved damage does not recursively create
  another authoritative damage request.
* Implement real-time authoritative damage only after spawn/death/reward is
  stable; it has a materially higher concurrency and latency risk.

### Dependency and licensing

* Use an optional gateway with `compileOnly`; do not shade MythicMobs.
* Pin the exact premium build/hash and validate every upgrade on the test
  server.
* Keep the premium JAR out of Git, public images, and public artifacts. Licenses
  bundled under `META-INF` may belong to dependencies and do not establish
  MythicMobs Premium redistribution rights.

## MMOCore decision

### Confirmed conflict

MMOCore's persistent `PlayerData` owns level, class, skill points, skill tree,
attributes, health, mana, stamina, stellium, professions, quests, waypoints,
friends, party, guild, combat state, and unlocks. Its default configuration
also enables auto-save, experience-bar override, action bars, resources,
parties, guilds, custom mining, and its quest system.

That model conflicts with:

* account/current-life/reincarnation separation
* cultivation stage and technique progression
* custom quest authority and idempotent rewards
* Game Service-authoritative combat and loot
* a single source of truth for player state

The plugin is source-visible but licensed All Rights Reserved, and it requires
MythicLib. The supplied snapshot cannot be meaningfully runtime-tested until a
matching legally obtained MythicLib build is available.

### Feasible approaches

#### A. Do not install MMOCore (selected)

Use Citizens + MythicMobs and build the missing ImmortalMC quest/cultivation
interfaces directly. This preserves the architecture and minimizes runtime,
licensing, migration, and upgrade coupling.

Pros: one authority, smallest version matrix, clean reincarnation model.

Cons: ImmortalMC must implement its own skill-binding UI, waypoints, and social
features when they become necessary.

The user selected this approach on 2026-07-13. MMOCore is not part of the
planned runtime stack, and no isolated MMOCore PoC is currently scheduled.

#### B. Isolated single-feature MMOCore PoC

Only when a specific gap becomes expensive, test one peripheral capability such
as waypoint presentation or skill binding. Game Service decides eligibility,
cost, skill availability, and result. MMOCore state must be disposable and
rebuildable.

Pros: may reuse mature UI/interaction work.

Cons: MythicLib hard dependency, broad listeners/default behavior, commercial
license constraints, and substantial proof needed to show unused systems are
truly disabled.

#### C. Adopt MMOCore as the RPG foundation

Map cultivation onto classes/levels/resources and accept MMOCore persistence as
primary or synchronize it with Game Service.

Pros: fastest route to a conventional Western-style RPG feature set.

Cons: contradicts the approved ImmortalMC design, creates dual writes or forces
a redesign of reincarnation/cultivation, and produces high migration lock-in.
This approach is not recommended.

## Staged roadmap

### Stage 1: Citizens identity adapter

1. Add a typed external target (`provider=citizens`, persistent NPC UUID).
2. Add optional Citizens capability detection and click routing.
3. Skip Citizens NPCs in the generic Bukkit entity interaction listener.
4. Migrate or recreate the existing `old-man` binding.
5. Restart the server and prove the binding survives NPC despawn/respawn and
   full restart without duplicate dialogue.

### Stage 2: First Mythic mob slice

1. Define one ImmortalMC mob template ID mapped to one Mythic internal name.
2. Spawn it through a thin Mythic gateway.
3. Observe spawn/death and create an idempotent Game Service reward endpoint.
4. Disable local drops and prove exactly-once reward/quest progress.
5. Test Game Service timeout, player disconnect, duplicate death delivery, and
   server restart.

### Stage 3: Custom quest state

1. Add Game Service quest definition/progress contracts.
2. Citizens dialogue accepts/advances the quest.
3. Mythic death facts advance objectives.
4. Game Service commits rewards and emits the presentation result.

### Stage 4: Combat authority

Add authoritative damage one action category at a time after measuring latency
and proving thread-safe cancellation/application. Prefer action-level plans for
multi-hit skills instead of an HTTP round trip for every visual hit.

### Stage 5: Reassess missing peripheral features

Only then evaluate whether waypoints, skill-binding UI, party UI, or another
isolated capability justifies an MMOCore PoC or a smaller dedicated plugin.

## Release gates

* Exact plugin builds and checksums recorded; premium artifacts remain private.
* Server boots with each optional plugin present and absent.
* No `NoClassDefFoundError`, `NoSuchMethodError`, severe startup errors, or
  duplicate interaction delivery.
* Citizens binding survives restart using persistent NPC UUID.
* Mythic reward and quest progress are idempotent and fail closed when Game
  Service is unavailable.
* No local/plugin state can override authoritative quest, combat, loot,
  cultivation, or reincarnation data.
* Rollback consists of disabling the optional adapter/plugin without corrupting
  Game Service state.

## Source research

* [Citizens integration research](citizens-integration.md)
* [MythicMobs integration research](mythicmobs-integration.md)
* [MMOCore integration research](mmocore-integration.md)
