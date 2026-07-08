# Plugin Ecosystem Evaluation For Interaction-Driven Gameplay

## Sources Checked

Official documentation:

* CMI Interactive Commands:
  `https://www.zrips.net/cmi/commands/interactive-commands/`
* CMI Attached Commands:
  `https://www.zrips.net/cmi/commands/attached-commands/`
* ItemsAdder first install:
  `https://itemsadder.devs.beer/plugin-usage/first-install.md`
* ItemsAdder item events/actions:
  `https://itemsadder.devs.beer/adding-content/items/item-properties/events.md`
  and `https://itemsadder.devs.beer/adding-content/items/item-properties/actions.md`
* ItemsAdder Java API/events:
  `https://itemsadder.devs.beer/developers/java-api.md`
  and `https://itemsadder.devs.beer/developers/java-api/events.md`
* MythicMobs API wiki:
  `https://git.mythiccraft.io/mythiccraft/MythicMobs/-/wikis/API/raw`

Local jars checked under `minecraft-nodes/main-plugin/newplugins/`:

* `CMI-9.8.8.1.jar`
* `CMILib1.5.9.9.jar`
* `ItemsAdder_4.0.16.jar`
* `MythicMobsPremium-5.13.0--SHOT.jar`
* `ProtocolLib.jar`

## Local Jar Metadata

* CMI `9.8.8.1`
  * `depend: [CMILib]`
  * `api-version: 1.13`
  * `folia-supported: true`
* CMILib `1.5.9.9`
  * Required by CMI.
* ItemsAdder `4.0.16`
  * `depend: [ProtocolLib]`
  * `api-version: 1.14`
  * `load: POSTWORLD`
  * Official install docs say ItemsAdder v4 is for `1.20.6 and greater`,
    and require `ProtocolLib.jar` in the server plugins folder.
* ProtocolLib `5.4.1-SNAPSHOT-1257506`
  * `load: STARTUP`
  * `api-version: 1.13`
* MythicMobs `5.13.0-SNAPSHOT-850a23db`
  * No hard depend in `plugin.yml`
  * `folia-supported: true`

## Plugin Roles

### CMI

CMI has two relevant official features:

* Interactive Commands can bind one named interaction to blocks or entities and
  run configured commands when a player interacts. The docs describe creating
  one with `/cmi ic new [name]`, assigning the looked-at block/entity, and
  adding one or more commands. CMI supports variables such as `[playerName]`.
* Attached Commands can attach one or more commands to item use. The docs list
  variables such as `[interactedBlock]` and `[interactedEntity]`, console
  execution via `!cc!`, click gating such as `!right!` and `!left!`, cooldowns,
  limited uses, and consume-only behavior.

Good fit:

* Fast admin-authored prototypes.
* Simple interaction -> command wiring.
* One-off utility interactions where testability is not critical.

Poor fit:

* Authoritative progression logic.
* Flows that need typed API boundaries, async Game Service calls, structured
  logs, idempotency, retries, and tests.
* Long command chains that become hard to review, version, and debug.

### ItemsAdder

ItemsAdder is primarily a custom content/resource-pack layer. Official docs
cover custom items, custom blocks, furniture, HUDs, sounds, and resource-pack
hosting. Item docs include events/actions; an `interact.right` event can run
actions such as `execute_commands`, with cooldown indicators and delayed
actions. The Java API docs expose lifecycle and resource-pack events such as
`ItemsAdderLoadDataEvent` and `ResourcePackSendEvent`.

Good fit:

* Custom visual items, blocks, furniture, HUDs, sounds, and resource-pack
  managed presentation.
* Giving the cultivation altar, talismans, weapons, or UI their final visual
  identity.
* Optional adapter integration when we need to recognize ItemsAdder custom
  content IDs from our own plugin.

Poor fit:

* Owning cultivation rules, persistence, stat progression, rewards, or combat
  authority.
* First MVP if we only need one interaction trigger; it adds resource-pack
  setup and ProtocolLib compatibility to the test surface.

### MythicMobs

MythicMobs is the right layer for custom mob definitions, skills, triggers,
spawning, loot presentation, and mob lifecycle hooks. Official API examples
show spawning Mythic mobs, checking whether a Bukkit entity is a Mythic mob,
getting `ActiveMob` instances, registering custom mechanics/conditions/targeters,
and registering custom skill triggers. Its Bukkit events include
`MythicMobInteractEvent`, `MythicDamageEvent`, `MythicMobDeathEvent`,
`MythicMobLootDropEvent`, and `MythicPlayerAttackEvent`.

Good fit:

* Custom monsters, bosses, skills, spawners, mob interaction, combat effects,
  and combat presentation.
* Integrating combat events into ImmortalMC progression once combat rules are
  defined.

Poor fit:

* Non-combat core account/life/spirit-root authority.
* Replacing the Game Service as the source of truth for persistent progression.

## Architecture Recommendation

Use a hybrid architecture:

* ImmortalMC plugin and Game Service own authoritative gameplay:
  account/session state, life state, spirit-root detection, progression,
  rewards, validation, idempotency, async service calls, and structured logs.
* Existing mature plugins own content and presentation where they are strongest:
  * CMI for quick prototypes and simple admin-configured command triggers.
  * ItemsAdder for custom visual items, blocks, furniture, HUDs, sounds, and
    resource-pack content.
  * MythicMobs for mobs, boss skills, combat triggers, mob drops, and combat
    presentation.
* Bridge plugins through explicit integration points instead of command-chain
  gameplay:
  * Native Paper listeners for core triggers.
  * Optional console-safe/internal ImmortalMC commands for CMI or ItemsAdder
    config to call.
  * Optional ItemsAdder/MythicMobs API listeners when their IDs/events are
    needed.

This avoids two extremes:

* Not everything is hardcoded Java. World/content configuration should remain
  data-driven.
* Not everything is plugin command chains. Core MMO rules should remain
  testable, logged, and owned by our code and Game Service.

## API-First Integration Strategy

Developing against these plugins' APIs is possible and useful, but should be
selective. "CMI has 300+ features" is a product-scope fact, not by itself a
reason to make CMI the center of ImmortalMC's architecture.

Recommended dependency policy:

* Use `compileOnly` dependencies for optional plugin APIs.
* Use `softdepend` in `plugin.yml` for optional integrations that need load
  order, and guard runtime registration with `PluginManager#getPlugin(...)`.
* Keep external API types out of ImmortalMC's core gameplay service contracts.
  Put them behind small adapter/facade classes such as `CmiIntegration`,
  `ItemsAdderIntegration`, and `MythicMobsIntegration`.
* Prefer domain APIs when they match the domain:
  * Paper API for basic block/item/entity interactions.
  * ItemsAdder API for custom item/block/furniture identity and events.
  * MythicMobs API for mobs, skills, mob events, and combat hooks.
  * CMI API for CMI-owned server-management features such as CMI user data,
    worth/economy, portals/warps, hologram interactions, or CMI events.
* Prefer widely adopted neutral APIs when available. For example, use Vault or
  a future economy abstraction for economy semantics instead of binding core
  progression directly to CMI Economy.

### CMI API Specifics

The official CMI API page points to `github.com/Zrips/CMI-API` and shows a
JitPack dependency:

* `com.github.Zrips:CMI-API:9.8.6.4` with `scope/provided`
* `CMIUser user = CMIUser.getUser(player)`
* managers accessed through `CMI.getInstance().get[managerName]()`
* examples for Worth Manager item buy/sell prices
* CMI custom events such as AFK, armor change, teleport, hologram click,
  portal use, PvP/PvE start/end, warp, balance change, etc.

The local CMI jar also contains many `com/Zrips/CMI/events/*` classes and CMI
hologram interaction events.

Good CMI API use cases for ImmortalMC:

* Integrating with CMI portals/warps if the server uses them for travel.
* Listening to CMI hologram/fake-entity interaction events if CMI holograms
  become part of the world UX.
* Reading CMI worth/economy data only if we intentionally choose CMI as an
  economy/content source.
* Reacting to CMI events for compatibility, logging, or presentation.

Poor CMI API use cases:

* Making CMI the source of truth for cultivation progression, combat stats,
  spirit roots, life cycles, or persistent player state.
* Wrapping hundreds of CMI commands/features "just in case".
* Calling CMI commands as a substitute for typed gameplay interfaces where we
  need tests, idempotency, and Game Service authority.

### ItemsAdder API Specifics

The local ItemsAdder jar exposes API classes and events including
`CustomStack`, `CustomBlock`, `CustomFurniture`, `CustomBlockInteractEvent`,
`FurnitureInteractEvent`, `ItemsAdderLoadDataEvent`, and
`ResourcePackSendEvent`.

Good ItemsAdder API use cases:

* Treating a namespaced custom block/furniture/item as a typed trigger, e.g.
  `immortal:spirit_root_altar`.
* Rendering custom HUD/resource-pack presentation after authoritative Game
  Service state changes.

### MythicMobs API Specifics

The MythicMobs API is strong and domain-specific for mobs/combat. Official docs
and local jar expose mob managers, active mobs, custom mechanics/conditions,
skill triggers, and Bukkit events such as `MythicMobInteractEvent`,
`MythicDamageEvent`, `MythicMobDeathEvent`, and `MythicPlayerAttackEvent`.

Good MythicMobs API use cases:

* Detecting Mythic mob death/damage/interaction events and forwarding relevant
  facts to ImmortalMC/Game Service.
* Exposing ImmortalMC custom skill mechanics/triggers later so MythicMobs YAML
  can trigger visuals or combat effects without owning persistent progression.

## Feasible Approaches For The Spirit-Root MVP

### Approach A: Native ImmortalMC Interaction Registry (Recommended)

ImmortalMC adds a config-driven trigger registry and a native Paper listener.
For the first slice, one configured block/location triggers the existing
Game Service spirit-root detection flow.

Pros:

* Keeps core behavior testable and logged.
* No new runtime dependency for this first interaction.
* Still avoids hardcoding locations by using our own config.
* Reuses the current session cache and Game Service call.
* Leaves room to add ItemsAdder/MythicMobs IDs as trigger types later.

Cons:

* Requires us to build a small interaction registry instead of using a GUI
  command editor.
* World builders edit our config until we add better tooling.

### Approach B: CMI Trigger Calling ImmortalMC Internal Command

CMI Interactive Commands binds the altar block/entity and calls a new
ImmortalMC internal, console-safe command such as
`/immortalmc-internal trigger spirit_root_detection <player>`.
ImmortalMC still owns the actual detection logic.

Pros:

* Very fast to configure in-game.
* Good for prototyping multiple blocks/entities.
* Uses a mature plugin for the click binding.

Cons:

* Adds CMI/CMILib as a required dependency for the first core flow.
* More permission/security care is needed because the trigger arrives as a
  command.
* The interaction definition lives in CMI config, so tests and code review cover
  less of the real behavior.
* Debugging crosses plugin config plus our code.

### Approach C: Plugin-Heavy Content Layer From The Start

Use ItemsAdder for a custom altar/item/furniture trigger and possibly CMI or
ItemsAdder actions to call ImmortalMC.

Pros:

* Best visual direction for a polished MMORPG presentation.
* Gets resource-pack workflows started early.

Cons:

* Larger first-slice setup: ItemsAdder, ProtocolLib, resource-pack hosting, and
  compatibility smoke tests.
* More moving parts before the core flow is stable.
* Still needs ImmortalMC/Game Service authority behind the trigger.

## Decision Pressure

The next implementation choice is not "pure code vs plugins". The useful
boundary is:

* Core rules and persistence stay in ImmortalMC/Game Service.
* Trigger/content/presentation can be native config, CMI config, ItemsAdder
  content, or MythicMobs config depending on the domain.

For the next MVP, the lowest-risk path is Approach A. Approach B is acceptable
if fast in-game authoring is more important than reducing dependencies in this
first slice.
