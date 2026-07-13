# Citizens 2.0.43-b4211 integration research

Research date: 2026-07-13

## Executive decision

Use Citizens as the NPC runtime and presentation layer, while ImmortalMC remains
the owner of dialogue, quests, cultivation state, rewards, and authorization.

The first integration should be an optional Citizens adapter, not a rewrite of
the working dialogue engine and not a custom fork of Citizens:

1. Citizens owns NPC creation, entity lifecycle, skins, nameplates, looking,
   navigation, and its own NPC persistence.
2. ImmortalMC stores a binding from the stable Citizens NPC UUID to an
   ImmortalMC interaction/dialogue/quest-giver ID.
3. ImmortalMC listens to `NPCRightClickEvent`, resolves the binding, and routes
   into the existing `EntityInteractionActionRouter` / dialogue presenter.
4. MythicMobs owns combat mobs and encounter mechanics. Citizens NPCs should
   remain non-combat actors by default.

Do not make Bukkit entity UUID the long-term identity of a Citizens NPC. The
domain key should be `NPC#getUniqueId()`; keep `NPC#getId()` only as an admin
display/convenience value.

## Artifact and compatibility findings

The supplied artifact is:

- `plugins-new-add/Citizens-2.0.43-b4211.jar`
- SHA-256: `aea786c361ce88bfc6c0a98214100d836321341a5e01e0281147cbd57a7683c6`
- Embedded plugin version: `2.0.43-SNAPSHOT (build 4211)`
- Jenkins build time: 2026-07-03 04:11:56 (Jenkins display time)
- Citizens2 revision: `a5c3de1a4d17148ab66a0e773dd99db918f5f9fb`
- Embedded NMS modules include `v1_21_R7`, `v26_1_R1`, and `v26_2_R1`.

This is a development snapshot, not a semantic-versioned stable release. Pin
the exact build number and retain the jar checksum in deployment documentation.
Citizens is NMS-heavy, so a Paper/Minecraft update must be treated as a plugin
compatibility event even when the public API is unchanged.

The current server is Paper `1.21.11-132`, reporting NMS `v1_21_R7`. The real
startup log confirms build 4211 was remapped, loaded and enabled successfully,
loaded its libraries, and reported `Loaded 0 NPCs`; no Citizens startup error is
present. This is stronger evidence for the current environment than a generic
compatibility claim.

Build 4211's Jenkins page explicitly shows the `citizens-v1_21_R7` module built
successfully. The local JAR contains that module. Therefore build 4211 is a
good fit for the currently pinned Paper 1.21.11 server. Do not infer support for
a future Paper build from `api-version: 1.13`; that field only declares Bukkit
API compatibility behavior, not NMS compatibility.

The artifact manifest says `Build-Jdk-Spec: 25`, while the Citizens API module
is compiled with Java release 8. The actual plugin has already run on this
project's Java 21 server, so Java 21 is verified for this artifact. The manifest
value describes the build JDK and is not by itself a Java 25 runtime requirement.

## License and open-source status

Citizens2 and CitizensAPI publish source on GitHub. The supplied JAR embeds a
`LICENSE` file stating **Open Software License 3.0 (OSL-3.0)**. OSL-3.0 is an
OSI-approved open-source license, but it is reciprocal: distributing or
externally deploying a modified Citizens derivative carries source and license
obligations, including the license's external-deployment clause.

Operational consequence:

- Running the unmodified plugin and integrating through its public API is the
  lowest-risk option.
- Do not copy Citizens source into ImmortalMC or ship a private modified fork
  without a deliberate license review and source-publication process.
- Keep the Citizens license and provenance with the deployed third-party jar.
- This document is engineering guidance, not legal advice.

## NPC identity and lifecycle

Citizens exposes three identifiers that must not be conflated:

| Identifier | Meaning | Recommended use |
| --- | --- | --- |
| `NPC#getId()` | Registry-local integer ID; API docs say it is not guaranteed globally unique across server sessions | Admin commands/log display only |
| `NPC#getUniqueId()` | Persistent Citizens NPC UUID; API docs say it is unique for all NPCs | ImmortalMC binding and durable references |
| `NPC#getMinecraftUniqueId()` | Client/entity UUID; for PLAYER NPCs Citizens changes UUID version bits to signal an NPC | Never store as the domain identity |

Build 4211 source shows that normal NPC creation generates a random UUID and a
store-generated integer ID. The persistent UUID is written to Citizens storage.
On spawn, non-player NPC entities receive `NPC#getUniqueId()` as their Bukkit
entity UUID. Player NPCs receive `NPC#getMinecraftUniqueId()`, which is a
version-bit-modified form of the persistent UUID. Registry lookup normalizes
that player-NPC UUID back before lookup.

The practical result is:

- Citizens NPC object identity survives despawn/respawn and server restart.
- The current ImmortalMC `EntityBinding(worldName, entityUuid)` happens to work
  for many non-player Citizens NPCs, but it is the wrong abstraction for player
  NPCs and makes Citizens lifecycle semantics implicit.
- Add a Citizens-specific binding such as `CitizensNpcBinding(UUID npcUuid)` or
  a typed external reference (`provider=citizens`, `externalId=<npc UUID>`).
- Resolve a click from the Citizens event's `event.getNPC()` instead of trying
  to rediscover it from the Bukkit entity.
- Do not add the world name to Citizens identity. A Citizens NPC can move or be
  respawned in another world while retaining its persistent UUID.

Lifecycle operations differ materially:

- `npc.despawn(reason)` removes the live Bukkit entity but retains the NPC and
  its stored definition.
- `npc.spawn(location, reason)` creates the live entity and emits
  `NPCSpawnEvent` after Paper considers it valid.
- `npc.destroy()` emits `NPCRemoveEvent`, removes traits, deregisters the NPC,
  despawns it with `REMOVAL`, and clears its datastore entry.
- `NPCRegistry#deregister(npc)` also clears datastore data and should not be
  used as a harmless despawn.

On `NPCRemoveEvent`, ImmortalMC should delete or mark stale every binding for
that Citizens UUID. On `NPCSpawnEvent`, it may refresh caches/presentation, but
it should not create duplicate domain bindings. On `NPCDespawnEvent`, retain
the domain binding because a later respawn is expected.

## Click and lifecycle events

For dialogue/quest interaction, use Citizens events rather than the generic
`PlayerInteractEntityEvent` path:

- `NPCRightClickEvent`: primary dialogue trigger; exposes `getNPC()` and
  `getClicker()` and filters off-hand duplicates inside Citizens.
- `NPCLeftClickEvent`: optional future attack/inspect interaction.
- `NPCSpawnEvent`: cancellable; exposes `SpawnReason` and location.
- `NPCDespawnEvent`: cancellable except Citizens does not honor cancellation
  for death; exposes `DespawnReason`.
- `NPCRemoveEvent`: non-cancellable final removal signal.

Citizens fires `NPCRightClickEvent` at `HIGHEST` priority after resolving click
redirection. If the Citizens event is cancelled, Citizens cancels the original
Bukkit interaction. Its separate `delayedCancellation` flag is used to suppress
the underlying vanilla interaction after Citizens traits/commands handle it.

Recommended listener behavior:

```java
@EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
public void onNpcRightClick(NPCRightClickEvent event) {
    Optional<EntityInteractionDefinition> binding =
            registry.findByCitizensNpcUuid(event.getNPC().getUniqueId());
    if (binding.isEmpty()) {
        return;
    }

    event.setDelayedCancellation(true);
    router.route(binding.get(), new BukkitEntityInteractionContext(
            event.getClicker(), event.getNPC().getEntity()));
}
```

Use an explicit per-player conversation guard/cooldown because two fast clicks
can still start two ImmortalMC sessions. Do not depend on listener priority as a
deduplication mechanism.

During migration, the generic `PlayerInteractEntityEvent` listener must skip
Citizens NPCs when the Citizens adapter is active, otherwise the same click can
route once through ImmortalMC's generic listener and once through
`NPCRightClickEvent`. A no-link fallback check can use `entity.hasMetadata("NPC")`,
which the official Citizens API guide documents and the build 4211 source sets.
When Citizens API is available, prefer `CitizensAPI.getNPCRegistry().isNPC(entity)`.

## Dependency and startup model

Use the official Citizens Maven repository and a `compileOnly` dependency. The
official wiki specifically warns not to shade Citizens and recommends the
`citizens-main` artifact rather than `citizensapi`, because built-in traits such
as `SkinTrait` live in the main module.

```kotlin
repositories {
    maven("https://maven.citizensnpcs.co/repo")
}

dependencies {
    compileOnly("net.citizensnpcs:citizens-main:2.0.43-SNAPSHOT") {
        isTransitive = false
    }
}
```

Keep the runtime jar supplied by deployment; do not package it into the
ImmortalMC jar. For reproducible compilation, prefer a dependency lock or a
locally published/checksummed API artifact because `-SNAPSHOT` can change under
the same coordinate. An even stricter option is a small internal interface plus
a separate Citizens adapter source set/module compiled against the pinned jar.

Use `softdepend: [Citizens]` because the user requires graceful degradation. In
`onEnable`:

1. Check whether plugin `Citizens` exists and is enabled.
2. Check `CitizensAPI.hasImplementation()` before any API call.
3. Register any custom trait immediately, before Citizens' delayed load task.
4. Register a `CitizensEnableEvent` listener and reconcile persisted bindings
   when it fires.
5. Also make activation idempotent for hot-load/test scenarios where Citizens
   is already fully loaded.

Build 4211 schedules its NPC datastore load one tick after Citizens `onEnable`
and fires `CitizensEnableEvent` after NPCs are loaded. The official API wiki
also mentions `CitizensLoadEvent`, but that class is absent from the supplied
2.0.43-b4211 JAR; do not compile against that stale wiki reference.

Missing-plugin behavior should be explicit:

- ImmortalMC still starts, health checks work, and non-Citizens interactions
  continue to function.
- Citizens-backed bindings are loaded but reported as unavailable, not deleted.
- Admin commands that create/select Citizens NPCs return a clear
  `Citizens integration unavailable` result.
- Startup logs contain one structured capability line, not repeated stack traces.
- Code that references Citizens classes must only load on the enabled branch;
  isolate it behind an adapter/factory so JVM class loading does not throw
  `NoClassDefFoundError` when Citizens is absent.

## Persistence ownership and traits

Citizens' default registry persists NPC definitions and traits in its datastore
(`plugins/Citizens/saves.yml` by default). `NPC#save(DataKey)` stores the NPC
UUID, metadata and all attached trait data. `NPCRegistry#saveToStore()` requests
an immediate registry save. Normal server/plugin shutdown also saves data.

ImmortalMC should not edit `Citizens/saves.yml` directly. All Citizens changes
must go through the API, and ImmortalMC should keep its own binding/config data
as the domain source of truth.

Recommended binding record:

```yaml
interactions:
  - id: old-man-dialogue
    action: npc-dialogue
    target:
      provider: citizens
      npc-uuid: 00000000-0000-0000-0000-000000000000
    metadata:
      dialogue-id: old-man
```

A custom trait is optional, not required for MVP. If added later, keep it thin:

- `@TraitName("immortal")`
- fields such as stable `interactionId` or presentation flags via `@Persist`
- no player quest progress and no authoritative rewards in Citizens storage
- register with `CitizensAPI.getTraitFactory().registerTrait(TraitInfo.create(...))`
- account for `onAttach`, `load`, `onSpawn`, `onDespawn`, and `onRemove`

The official guide notes traits are Bukkit listeners and a `run()` override can
execute every tick. Avoid one high-frequency event handler or tick loop per NPC;
use a shared ImmortalMC listener and registry for dialogue. This reduces event
fan-out and makes the quest plugin independent of Citizens save-file structure.

## Skins and navigation

Citizens should replace custom NPC skin and navigation work.

For player skins, use `SkinTrait` from `citizens-main`. The official skin guide
recommends setting the skin before `npc.spawn()` so the initial default-skin
lookup cannot delay or overwrite the desired skin. For production content,
prefer pre-generated texture/signature data with
`setSkinPersistent(uniqueId, signature, texture)` over runtime image-URL
conversion. Mojang/Mineskin calls can be rate-limited or unavailable; external
skin service failure must not prevent quest logic from loading.

Skin prerequisites/risks include online mode, outbound access, Mojang service
availability, and rate limits. Cache and reuse texture/signature blobs in
content configuration where licensing permits.

For movement, use `npc.getNavigator().setTarget(location)` once per navigation
request. Listen for navigation begin/cancel/complete events. Citizens documents
two parameter scopes: default parameters persist for the NPC, while local
parameters apply to the current target. Set local speed/range parameters after
setting the target unless a permanent NPC default is intended.

Do not issue `setTarget` every tick. Do not pathfind during an active blocking
dialogue unless the design calls for it. Decide whether a quest giver pauses,
faces the player, or continues its patrol, then encode that in the adapter.

## Relationship with MythicMobs

The current startup log says `Mythic Citizens Support has been enabled!`, so the
installed MythicMobs 5.13.0 snapshot detects Citizens successfully.

The local MythicMobs JAR's `CitizensSupport#isCitizensNPC` checks the Bukkit
entity metadata key `NPC`. Its configuration and official wiki expose
`TargetCitizensNPCs: false` plus targeter filters for Citizens NPCs. Keep that
default false so combat skills do not accidentally target quest givers.

Recommended ownership boundary:

- Citizens: named persistent NPC actors, skins, movement/patrol, presentation.
- ImmortalMC: dialogue, quests, requirements, progress, choices, rewards,
  cultivation rules, and authoritative state.
- MythicMobs: enemies, bosses, skills, drops, encounter phases, and spawners.

Do not make the same actor simultaneously a Citizens quest giver and a
MythicMobs `ActiveMob` unless a specific boss-NPC use case justifies the extra
lifecycle complexity. For a quest that starts combat, the Citizens click should
ask ImmortalMC to start the quest; ImmortalMC then requests a Mythic mob/spawner
by stable Mythic internal name. Persist the quest/encounter ID in ImmortalMC,
not the transient spawned mob UUID.

MythicMobs' wiki also describes building stationary NPC-like mobs directly in
MythicMobs. Do not use that pattern for normal ImmortalMC quest givers now that
Citizens is selected; it would create two NPC systems and duplicate click,
persistence, skin, and lifecycle rules.

## Proposed integration phases

### Phase 1: adapter and identity migration

- Add typed Citizens NPC binding keyed by `NPC#getUniqueId()`.
- Add optional Citizens capability detection and safe classloading boundary.
- Add `NPCRightClickEvent` routing to the existing dialogue action.
- Skip Citizens entities in the generic Bukkit interaction listener.
- Add admin binding command that resolves the looked-at entity through
  `NPCRegistry#getNPC(entity)` and stores the persistent NPC UUID.
- Keep legacy world/entity UUID bindings readable for existing non-Citizens
  dialogue entities; provide an explicit migration command rather than silently
  rewriting them.

### Phase 2: NPC provisioning and presentation

- Create/select Citizens NPCs through API or Citizens admin commands.
- Add skin-before-spawn handling, look-close/face-player behavior, and optional
  navigation/patrol integration.
- Reconcile bindings after `CitizensEnableEvent` and warn for missing UUIDs.

### Phase 3: quest and encounter orchestration

- Keep quest definitions and player progress inside ImmortalMC.
- Trigger MythicMobs encounters through a narrow Mythic adapter.
- Correlate Mythic death/despawn events back to an ImmortalMC encounter ID.

## Test plan

Unit tests without a running Citizens server:

- Citizens UUID binding serialization and legacy binding compatibility.
- Router invokes dialogue once for one Citizens right-click.
- Off-hand/generic Bukkit path does not duplicate Citizens routing.
- Missing binding is a no-op.
- Missing Citizens capability leaves ImmortalMC enabled.
- NPC remove deletes/invalidates the matching binding; despawn does not.
- Activation is idempotent across enable/reload callbacks.

Adapter contract tests with a fake gateway:

- `getPersistentUuid` uses `NPC#getUniqueId`, never Bukkit entity UUID.
- Player-NPC client UUID differences do not change lookup.
- Missing/stale UUID produces a diagnostic and preserves config for repair.

Paper integration checks on the pinned local server:

1. Start with Citizens absent: ImmortalMC enables and non-Citizens functions work.
2. Start with Citizens 4211: no linkage errors; capability reports enabled.
3. Create PLAYER and VILLAGER NPCs, bind both, restart, and confirm both still
   route to the same dialogue.
4. Despawn/respawn and move an NPC across worlds; binding remains valid.
5. Destroy an NPC; stale binding is reported/cleaned according to policy.
6. Rapid double-click and main/off-hand interaction produce one conversation.
7. Set a skin before spawn; restart and confirm it persists.
8. Navigate, cancel, unload/reload chunk, and confirm no stuck dialogue/session.
9. Run a Mythic skill/targeter near the quest giver and confirm
   `TargetCitizensNPCs: false` protects it.
10. Upgrade Citizens only after taking a backup of `saves.yml` and running this
    suite against the exact candidate build.

## Main risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Snapshot artifact changes under the same Maven version | Pin build 4211/checksum; dependency lock or local artifact |
| Paper NMS update breaks Citizens | Treat Paper upgrades as coordinated Citizens upgrades; test exact pair |
| Binding to Bukkit/world identity breaks player NPCs or movement | Persist Citizens `NPC#getUniqueId()` only |
| Duplicate generic and Citizens click listeners | Skip Citizens in generic listener; single session guard |
| Custom trait registered after NPC datastore load | Register during ImmortalMC `onEnable`; reconcile on `CitizensEnableEvent` |
| Citizens absent causes classloading failure | Isolate adapter classes and instantiate only after capability check |
| NPC removed while quest binding remains | Handle `NPCRemoveEvent`; startup stale-binding audit |
| Skin service outage/rate limit | Pre-store signed textures; presentation failure must not block quests |
| Pathfinding cost or repeated target resets | One navigation request; local parameters; completion/cancel handling |
| Mythic skills damage/target quest NPCs | Keep `TargetCitizensNPCs: false`; integration test target filters |
| OSL-3.0 obligations from a modified fork | Use unmodified binary/public API; review before forking/distributing |
| Wiki/API drift | Verify against pinned local JAR and exact source revision each upgrade |

## Sources

Primary Citizens sources:

- Build 4211 Jenkins record and artifact metadata:
  https://ci.citizensnpcs.co/job/Citizens2/4211/
- Exact Citizens2 build revision:
  https://github.com/CitizensDev/Citizens2/commit/a5c3de1a4d17148ab66a0e773dd99db918f5f9fb
- Citizens2 source repository and OSL-3.0 license:
  https://github.com/CitizensDev/Citizens2
- CitizensAPI source repository:
  https://github.com/CitizensDev/CitizensAPI
- Citizens API guide (dependency, lifecycle, traits, navigation, persistence):
  https://wiki.citizensnpcs.co/API
- Citizens Javadocs:
  https://jd.citizensnpcs.co/
- Citizens skin guide:
  https://wiki.citizensnpcs.co/Skins
- Citizens waypoints guide:
  https://wiki.citizensnpcs.co/Waypoints
- Exact API source used to verify identifier semantics (artifact timestamp and
  Jenkins-resolved API snapshot align with this 2026-06-20 revision):
  https://github.com/CitizensDev/CitizensAPI/blob/a4d3643ea89bb4ee9e7ea892fbdfae55b1c03954/src/main/java/net/citizensnpcs/api/npc/NPC.java
- Registry API:
  https://github.com/CitizensDev/CitizensAPI/blob/a4d3643ea89bb4ee9e7ea892fbdfae55b1c03954/src/main/java/net/citizensnpcs/api/npc/NPCRegistry.java
- Click/lifecycle events:
  https://github.com/CitizensDev/CitizensAPI/tree/a4d3643ea89bb4ee9e7ea892fbdfae55b1c03954/src/main/java/net/citizensnpcs/api/event
- Trait/persistence source:
  https://github.com/CitizensDev/CitizensAPI/tree/a4d3643ea89bb4ee9e7ea892fbdfae55b1c03954/src/main/java/net/citizensnpcs/api

MythicMobs sources/evidence:

- Official MythicMobs wiki repository:
  https://git.mythiccraft.io/mythiccraft/MythicMobs.wiki
- Targeter documentation (Citizens NPC filters):
  https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Skills/Targeters
- MythicMobs stationary NPC guide, evaluated and intentionally not selected for
  normal quest givers:
  https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/Guides/Making-an-NPC

Local verification evidence:

- `plugins-new-add/Citizens-2.0.43-b4211.jar`
- `plugins-new-add/MythicMobsPremium-5.13.0--SHOT.jar`
- `minecraft-nodes/main-server/logs/latest.log`
- `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalEntityInteractionListener.java`
- `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/content/EntityBinding.java`
- `minecraft-nodes/main-plugin/build.gradle.kts`

The official API wiki contains at least one stale reference for this pinned
build (`CitizensLoadEvent` is mentioned but absent from the JAR). Where wiki and
artifact differ, this research treats the supplied JAR and exact build source as
authoritative.
