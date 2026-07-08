# entity interaction management, starting with spirit-root detector

## Goal

Complete the admin-side management flow for in-world entity interaction points so server builders can create, inspect, remove, reload, protect, and route right-click interactions without relying on ad hoc manual config edits. Spirit-root detection is the first action using this system, not the infrastructure itself.

## What I already know

* Existing gameplay interaction is entity-bound: right-clicking a configured detector entity calls Game Service spirit-root detection and plays particles around the player/entity.
* Game Service remains authoritative for spirit-root rules. The Paper Adapter must not roll quality or elements.
* Existing commands are `/immortal spirit-root-detector set` and `/immortal spirit-root-detector reload`.
* Existing config path is `content.spirit-root.detectors`, currently a list of `{world, entity-uuid}` entries.
* User wants detector management completed with list/remove/create, persistent spawned entities, entity protection, and a formal config entry with `id`.
* User clarified that entity binding, interaction routing, and visual effects must not be hardcoded to spirit-root detection. Later NPC dialogue and other MMORPG interactions should reuse the same foundation.

## Assumptions

* Admin commands are acceptable for server editing; player gameplay remains interaction-driven rather than command-driven.
* The existing `/immortal spirit-root-detector ...` command remains as a spirit-root-specific authoring wrapper over the generic entity interaction registry.
* `/immortal spirit-root-detector remove` unbinds the looked-at detector from ImmortalMC config. It does not delete arbitrary existing entities bound via `set`.
* `/immortal spirit-root-detector create` spawns a protected Villager-style detector at the admin player's current location and binds it immediately to the `spirit-root-detect` action.
* Existing old-format config entries must continue to load and should be normalized to the new schema on the next save.

## Requirements

* Add generic entity interaction definitions with stable `id`, `action`, entity binding, entity type, and protection flag.
* Persist new data under a generic config path such as `content.entity-interactions.entries`.
* Preserve backward compatibility with legacy spirit-root detector config entries that only contain `world` and `entity-uuid`; load them as `spirit-root-detect` interactions when the new path is absent.
* Add admin commands:
  * `/immortal spirit-root-detector create`
  * `/immortal spirit-root-detector list`
  * `/immortal spirit-root-detector remove`
  * existing `set` and `reload` continue to work.
* `create` requires an in-game player, spawns a persistent protected detector entity, stores it in config as action `spirit-root-detect`, and logs the operation.
* `set` binds the looked-at existing entity to action `spirit-root-detect` and stores a generated interaction id.
* `list` returns current spirit-root detector ids and bindings by filtering generic interactions on action `spirit-root-detect`.
* `remove` requires a player looking at a configured spirit-root detector and removes only that interaction binding from config.
* Generic entity interaction listeners route right-clicks by `action` to registered handlers.
* Generic protection listeners protect configured entities from common environmental or accidental disruption: damage, death, combustion, teleport, movement, transform, and target events are cancelled when the configured entity is involved.
* Operational debug/admin details go to Paper logs at the appropriate level; player chat is limited to command results and gameplay feedback.

## Acceptance Criteria

* [x] Registry tests cover reload, action-filtered matching/listing, id generation, save deduplication, and removal.
* [x] Command parser tests cover create/list/remove/set/reload.
* [x] Admin runner tests cover player-only create/set/remove, target-missing remove/set, list output, create persistence, and removal persistence.
* [x] Resource/config tests cover the formal detector config fields.
* [x] Existing right-click detection still matches by `world + entity-uuid` but runs through a generic action handler.
* [x] Paper plugin builds against `io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT`.
* [x] Updated plugin jar is deployed into the local Paper server and the server is restarted cleanly.

## Definition of Done

* Tests added/updated.
* Gradle build passes with Java 21 and `--max-workers=1`.
* Paper server starts with the updated plugin.
* Specs are updated if the implementation establishes a new adapter convention.
* Changes are committed in a work commit, then Trellis task/archive/journal commits can follow.

## Out of Scope

* Full NPC editor UI, GUI menus, or third-party plugin adapter integration.
* Implementing dialogue/quest/shop actions beyond keeping the infrastructure ready for them.
* Deleting arbitrary existing entities on `remove`.
* Custom model/resource-pack integration for the spawned detector.
* Storing detector locations for automatic respawn after forceful external removal.

## Technical Notes

* Relevant code:
  * `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/content/`
  * `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/`
  * `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalEntityInteractionListener.java`
  * `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/EntityInteractionProtectionListener.java`
  * `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
* Relevant specs:
  * `.trellis/spec/backend/directory-structure.md`
  * `.trellis/spec/backend/logging-guidelines.md`
  * `.trellis/spec/backend/quality-guidelines.md`
  * `.trellis/spec/guides/cross-layer-thinking-guide.md`
  * `.trellis/spec/guides/code-reuse-thinking-guide.md`
* Local Paper API inspection confirmed these usable event/classes in 1.21.11:
  * `EntityDamageEvent`, `EntityCombustEvent`, `EntityDeathEvent`, `EntityTeleportEvent`, `EntityTransformEvent`, `EntityTargetEvent`
  * `io.papermc.paper.event.entity.EntityMoveEvent`
  * `World#spawn(Location, Class<T>, CreatureSpawnEvent.SpawnReason, boolean, Consumer<? super T>)`
  * entity persistence/protection methods including `setPersistent`, `setInvulnerable`, `setGravity`, and LivingEntity `setRemoveWhenFarAway`, `setAI`, `setAware`, `setCollidable`.
