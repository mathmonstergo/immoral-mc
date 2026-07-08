# brainstorm: Editable MMORPG Content Interaction Flow

## Goal

Move spirit-root detection from the temporary `/immortal spirit-root` command
toward a standard Minecraft MMORPG interaction flow: players should interact
with a bound in-world detector entity and receive intentional gameplay
feedback, including particle effects around both the detector entity and the
player, while Adapter debug/status details stay in Paper logs. Treat this as
the first vertical slice of a broader editable MMORPG content system for
ImmortalMC: monsters, items, entity interactions, triggers, effects, and world
placement should be authorable without changing Java code each time.

## What I already know

* The user wants a Wynncraft-like server flow where core gameplay does not rely
  on typed player commands.
* `/immortal spirit-root` exists only as a temporary development test entrypoint.
* Game Service owns authoritative spirit-root generation and persistence.
* The Adapter must not roll spirit-root quality/elements locally.
* Adapter operational events should use leveled Paper logs, not player chat.
* The local Paper test server is running on Minecraft/Paper `1.21.11`, port
  `25549`, with Game Service at `127.0.0.1:8000`.
* The user has placed CMI, CMILib, ItemsAdder, MythicMobs, and ProtocolLib jars
  under `minecraft-nodes/main-plugin/newplugins/` for evaluation.
* CMI supports interaction-driven command execution for blocks/entities and
  items.
* CMI also has an official `CMI-API` artifact and custom events/managers, but
  its broad feature count does not mean ImmortalMC should wrap or depend on all
  CMI features.
* ItemsAdder is mainly a custom content/resource-pack layer for items, blocks,
  furniture, HUDs, sounds, and related actions/API events.
* ItemsAdder exposes API classes/events for custom items, custom blocks,
  furniture, resource-pack lifecycle, and content identity.
* MythicMobs is the likely future layer for custom mobs, skills, combat
  triggers, and mob lifecycle integration.
* MythicMobs exposes a strong domain API for mobs, skills, custom triggers, and
  combat/mob lifecycle events.
* The user wants a Wynncraft-like server authoring model combined with a
  cultivation/xianxia ruleset: code implements reusable capabilities, while
  server-side content editing decides where/when/how those capabilities appear.
* The first gameplay trigger should bind to a specific entity rather than a
  static altar block.
* Spirit-root feedback should include particle effects around both the
  detector entity and the player, with different visual plans for different
  root qualities/elements.
* Server editing should feel like established Minecraft tooling where possible:
  command-driven, GUI-driven, or selection/wand-driven workflows instead of
  editing Java code.
* Public Wynncraft documentation indicates a similar separation: developers
  build technical features and infrastructure, while Game Masters and other
  content roles use YAML, a proprietary scripting language, WorldEdit,
  VoxelSniper, Blockbench, and internal/proprietary tooling to create content.

## Assumptions (temporary)

* MVP should reuse the current Game Service endpoint:
  `POST /api/v1/players/{account_id}/current-life/spirit-root`.
* MVP should keep `/immortal spirit-root` available as a dev fallback, but not
  make it the primary player flow.
* Mature external plugins should be used for content/presentation and admin
  tooling, not as the authoritative source for cultivation rules or persistent
  progression.
* External plugin APIs should be optional integration layers. Their types should
  not leak into ImmortalMC's core gameplay service contracts.
* Runtime content definitions should live in versionable config/data files, and
  in-game editor commands should write/update those definitions instead of
  becoming the only source of truth.

## Open Questions

* None for the first implementation slice.

## Research References

* [`research/paper-interaction-triggers.md`](research/paper-interaction-triggers.md)
  — Paper native events support block, item, and entity interactions; the MVP
  now uses a configured detector entity trigger.
* [`research/plugin-ecosystem-evaluation.md`](research/plugin-ecosystem-evaluation.md)
  — The recommended long-term strategy is hybrid: ImmortalMC/Game Service own
  authority, while CMI/ItemsAdder/MythicMobs provide optional trigger,
  presentation, API integration, and content tooling.
* [`research/wynncraft-content-authoring-model.md`](research/wynncraft-content-authoring-model.md)
  — Public Wynncraft information points to a custom engine plus data/script
  content model, not hardcoded Java for every piece of gameplay and not only
  generic plugin command chains.

## Research Notes

### Hybrid plugin ecosystem strategy

The useful boundary is not "pure code vs plugins":

* ImmortalMC plugin and Game Service own authoritative gameplay: login/session
  state, current life state, spirit-root detection, progression, validation,
  idempotency, async Game Service calls, and structured logs.
* CMI can be used for quick admin-authored interaction prototypes, especially
  block/entity/item -> command wiring.
* ItemsAdder should be used when we need custom visual items, blocks, furniture,
  HUDs, sounds, or resource-pack-managed presentation.
* MythicMobs should be used for custom mobs, boss skills, combat triggers, mob
  drops, and mob lifecycle integration.
* External plugin configs may call into ImmortalMC through explicit, safe
  integration points, but should not contain core cultivation rules.
* External plugin APIs can be used where they are domain-appropriate, but only
  behind small adapter/facade classes:
  `CmiIntegration`, `ItemsAdderIntegration`, `MythicMobsIntegration`, etc.
* Integration dependencies should normally be `compileOnly` plus `softdepend`,
  with runtime checks before registering listeners that use optional plugin
  APIs.

### Editable content authoring model

The elegant model is to split the server into four layers:

* **Core gameplay engine**: Java/Paper plugin plus Game Service. This owns
  typed capabilities such as spirit-root detection, cultivation progression,
  combat state, rewards, validation, persistence, async service calls, logs,
  and permissions.
* **Content definitions**: YAML/JSON/data files that describe monsters, items,
  interaction points, triggers, conditions, actions, cooldowns, messages,
  sounds, particles, and references to ItemsAdder/MythicMobs/CMI IDs.
* **Authoring tools**: admin commands, GUI editors, and selection/wand-style
  flows that create/update content definitions from inside the server. These
  tools are convenience layers; the saved config remains reviewable and
  versionable.
* **Plugin adapters**: optional bridges to ItemsAdder, MythicMobs, CMI, and
  neutral APIs such as Vault. Adapters translate external plugin events/content
  IDs into ImmortalMC trigger/action contracts.

Wynncraft's public model supports this direction at a larger scale: Developers
build technical features, Game Masters work with YAML and a proprietary
scripting language, Scripters use WynnScript for dynamic systems, Builders use
WorldEdit/VoxelSniper, and Modelers use Blockbench plus proprietary tooling for
resource-pack models and animations. ImmortalMC should copy that separation of
responsibilities, not attempt to clone their private tooling.

In practical terms: code should define what an `immortal:spirit_root_detection`
action does; config or an in-game editor should decide that a specific detector
entity, an ItemsAdder furniture ID, or a MythicMobs NPC interaction triggers
that action.

The initial content model can be small:

* `triggers`: entity right-click first; later block right-click and item use.
* `conditions`: permission, world/region, session present, once-per-life,
  cooldown.
* `actions`: call Game Service capability, send intentional feedback, play
  sound/particle, dispatch optional plugin presentation.
* `bindings`: native entity identity, native location/material, ItemsAdder
  namespaced ID, MythicMobs mob ID/event, CMI hologram/portal/event identifier.

### Feasible approaches

**Approach A: Native ImmortalMC interaction registry**

* How it works: ImmortalMC adds a config-driven trigger registry and native
  Paper listener. For the first slice, player right-clicks a configured
  detector entity and ImmortalMC calls the existing Game Service detection
  flow.
* Pros: keeps core behavior testable and logged; no new runtime dependency for
  this first interaction; avoids hardcoding by using our own config; leaves
  room for ItemsAdder/MythicMobs trigger types later.
* Cons: requires a small registry/listener instead of using CMI's in-game
  command editor.

**Approach B: Content engine plus admin authoring commands** (Recommended)

* How it works: implement the native detector-entity trigger as the first
  content definition type, plus admin commands such as "select looked-at
  entity" and "save as spirit-root detector" that write the config. Optional
  plugin API adapters stay behind stable ImmortalMC trigger/action contracts.
* Pros: matches Wynncraft-style content authoring; avoids command-chain
  gameplay; gives the user an in-server editing workflow; config remains
  reviewable; scales to monsters/items/entity interactions.
* Cons: more design work than config-only; needs careful permissions and reload
  behavior.

**Approach C: Native registry plus optional plugin API boundary**

* How it works: implement the native detector-entity trigger now, and also
  create the first optional integration boundary so later trigger types can be
  backed by ItemsAdder custom block/furniture IDs, MythicMobs entities/events,
  or CMI hologram/portal events without changing core gameplay services.
* Pros: sets the long-term architecture early; avoids command-chain gameplay;
  keeps plugin-specific APIs isolated.
* Cons: slightly more scaffolding before a visible gameplay improvement.

**Approach D: CMI trigger calling ImmortalMC internal command**

* How it works: CMI Interactive Commands binds a detector entity and calls a
  new ImmortalMC internal, console-safe trigger command. ImmortalMC still owns
  the detection logic.
* Pros: fast in-game authoring; good for prototypes and multiple simple
  interaction points.
* Cons: adds CMI/CMILib dependency to the first core flow; requires command
  security/permission care; the trigger definition lives outside tests/code
  review in CMI config.

**Approach E: Plugin-heavy presentation first**

* How it works: start with ItemsAdder custom detector/item/furniture and
  optional CMI/ItemsAdder command actions calling ImmortalMC.
* Pros: best visual path toward a polished MMORPG presentation.
* Cons: larger first-slice setup: ItemsAdder, ProtocolLib, resource-pack
  hosting, and compatibility smoke tests before the core flow is stable.

## Requirements (evolving)

* Player-triggered spirit-root detection must happen through right-clicking a
  bound in-world entity instead of typed commands.
* The first implementation should establish a reusable trigger/action shape
  that can later support monsters, items, entity interactions, and world
  content without rewriting core logic.
* Content placement and binding should be editable through config and,
  preferably, an in-game admin authoring workflow.
* Core spirit-root detection rules must remain owned by ImmortalMC/Game Service,
  even if the trigger originates from CMI, ItemsAdder, or another plugin later.
* The Adapter must require a successful login session from `PlayerSessionCache`.
* Detection must call Game Service asynchronously and display the returned
  result only after the authoritative response.
* Paper logs must record success, rejection, and failure events with stable
  event names.
* The first implementation should use ImmortalMC-owned content definitions and
  a native Paper listener. It should not require CMI, ItemsAdder, MythicMobs,
  or ProtocolLib to run.
* Admin authoring must provide a small in-game command path to save the entity a
  player is looking at as the first spirit-root detector binding.
* The saved detector binding must remain reviewable in server config/data files
  so future editing tools do not become the only source of truth.
* Successful detection must trigger a particle presentation plan around both
  the player and detector entity.
* Particle presentation must vary by the authoritative root result returned by
  Game Service. The Adapter may choose visuals from returned quality/elements,
  but it must not infer or reroll the root.

## Acceptance Criteria (evolving)

* [ ] A player can trigger spirit-root detection by right-clicking a configured
      detector entity.
* [ ] The spirit-root detector entity binding is represented as data/config,
      not hardcoded Java coordinates.
* [ ] An admin can create or update the first detector binding through the
      chosen authoring workflow.
* [ ] A player without a cached Game Service session fails closed with
      intentional feedback.
* [ ] Detection success displays the returned root quality/elements and does
      not reroll if already detected.
* [ ] Detection success plays particle effects around both the detector entity
      and player, with different effects for at least celestial, variant,
      dual/triple, and pseudo-root results.
* [ ] Operational events are visible in Paper logs.
* [ ] Existing `/immortal health` behavior stays intact.

## Technical Approach

Use Approach B: content engine plus admin authoring commands.

The first slice is intentionally small:

* Add an ImmortalMC-owned content definition for one or more spirit-root
  detector entity bindings.
* Register a native Paper entity-interaction listener that handles
  right-clicking a configured detector entity.
* Route detector interactions through the same authoritative Game Service
  detection behavior used by the temporary development command.
* Add admin command coverage for saving the entity a player is looking at as a
  detector binding and reloading the local content definition.
* Add a particle presentation planner that maps authoritative root quality and
  elements to effects around the player and detector entity.
* Keep third-party plugin integrations out of this slice except as documented
  future adapter boundaries.

## Capability Ownership Table

| Capability | Authority | Plugin role |
| --- | --- | --- |
| Spirit root generation and persistence | Game Service | None |
| Current life/player progression state | Game Service/PostgreSQL | None |
| In-world detector entity trigger registry | ImmortalMC Paper adapter | Future CMI/ItemsAdder/MythicMobs triggers may call into it |
| Admin editing of first detector binding | ImmortalMC Paper adapter | Future GUI/wand helpers can improve UX |
| Detector/player particle feedback | ImmortalMC Paper adapter presentation | Future ItemsAdder/MythicMobs effects may enrich it |
| Custom detector visuals, furniture, sounds, HUD | ImmortalMC content references | ItemsAdder presentation adapter |
| Custom mobs, boss skills, mob lifecycle hooks | ImmortalMC combat/reward rules | MythicMobs authoring and presentation adapter |
| Teleports, portals, holograms, server utilities | Server/plugin configuration | CMI may own non-core utility behavior |
| Economy tied to progression | Game Service ledger | Future Vault provider/adapters, not CMI as source of truth |

## Decision (ADR-lite)

**Context**: ImmortalMC needs a Wynncraft-like authoring model without turning
core xianxia rules into opaque third-party plugin configuration.

**Decision**: Build a small ImmortalMC content/action foundation first. The
spirit-root detector entity becomes the first data-driven interaction, backed
by native Paper events, Paper particle presentation, and Game Service
authority. CMI, ItemsAdder, MythicMobs, and Vault remain optional adapter layers
for future capabilities.

**Consequences**: The first slice takes slightly more code than wiring a CMI
command chain, but it keeps the gameplay contract testable, logged, reviewable,
and independent from closed-source plugin data schemas.

## Implementation Plan

1. Extract shared spirit-root detection behavior so both the temporary command
   and detector-entity listener use one service path.
2. Add content definition loading/saving for spirit-root detector entity
   bindings.
3. Add admin command support to save the looked-at entity as a detector and
   reload content definitions.
4. Add the Paper entity interaction listener and focused tests for trigger
   matching, session failure, and command fallback behavior.
5. Add a particle presentation planner and Paper executor for player/entity
   effects after authoritative detection succeeds.
6. Build the plugin jar and leave the local server ready for a Windows-client
   smoke test.

## Definition of Done (team quality bar)

* Tests added/updated at the adapter service/listener level.
* Gradle build/test passes for `minecraft-nodes/main-plugin`.
* Docs/specs updated if the interaction pattern becomes a reusable convention.
* Local Paper server can be used for a manual Windows-client smoke test.

## Out of Scope (explicit)

* Production NPC scripting system.
* Full quest/dialogue framework.
* Combat, cultivation progression beyond spirit-root detection.
* Full monster/item editor UI beyond the reusable trigger/action foundation.
* Public deployment or proxy/network configuration.

## Technical Notes

* Existing temporary command path:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/SpiritRootCommandRunner.java`
* Existing login cache:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/session/PlayerSessionCache.java`
* Existing Paper listener:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalPlayerJoinListener.java`
* Existing logging convention:
  `.trellis/spec/backend/logging-guidelines.md`
* Entity interaction events may have hand variants depending on entity type;
  interaction listeners should normally process only `EquipmentSlot.HAND` when
  the event exposes a hand.
* A shared adapter service should likely sit below both the temporary command
  and the new interaction listener so async Game Service calls, logging, and
  result formatting are not duplicated.
* If CMI is used as a trigger layer, the current `/immortal spirit-root` command
  should not be exposed directly as the gameplay trigger because it is an
  op/dev command. Add a separate internal trigger boundary with explicit caller
  checks.
* If ItemsAdder is used in this slice, first verify local startup compatibility
  for ItemsAdder `4.0.16` plus ProtocolLib `5.4.1-SNAPSHOT-1257506` on Paper
  `1.21.11`.
