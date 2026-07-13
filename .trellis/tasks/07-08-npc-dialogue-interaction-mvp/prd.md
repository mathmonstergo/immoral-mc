# npc dialogue interaction mvp

## Goal

Add the first non-spirit-root entity interaction action: right-clicking a configured NPC starts a stylized dialogue sequence. This should prove the generic entity interaction foundation can support future Wynncraft-style NPCs, quests, shops, and scripted interactions without adding new hardcoded listeners.

## What I already know

* User approved the next step as an NPC dialogue interaction MVP.
* Dialogue must feel highly stylized in Minecraft chat.
* The opening task/quest-style text should be tall enough to fill the MC client chat display height.
* NPC lines should appear sequentially after the opening text.
* Each NPC line should play a villager sound.
* Existing entity interaction infrastructure already routes `PlayerInteractEntityEvent` through `EntityInteractionActionRouter<BukkitEntityInteractionContext>`.
* Existing config has `content.entity-interactions.entries: []`.
* Existing interaction entries include `id`, `action`, `world`, `entity-uuid`, `entity-type`, `protected`, and `managed-entity`.
* Existing command handling only exposes `health`, `spirit-root`, and `spirit-root-detector`.
* User chose to add a binding command so NPC dialogue can attach to entities created by other plugins.
* Dialogue content should be authored as YAML configuration.
* User chose separate dialogue YAML files rather than putting all dialogue content in `config.yml`.
* User approved a simple YAML schema with `id`, `title`, `speaker`, `opening-lines`, and `lines`.
* MVP text formatting can use Minecraft `§` color/style codes directly; MiniMessage is deferred.
* User approved default pacing of about 1.5 seconds per NPC line.
* Villager sounds should account for pitch variation instead of using one flat pitch for every line.

## Assumptions (temporary)

* NPC dialogue is presentation-layer content in the Paper Adapter for this MVP; it does not change authoritative Game Service quest/player state yet.
* Dialogue content should be data-driven YAML, not hardcoded in Java.
* Binding a dialogue to an entity should reuse the existing entity interaction registry rather than adding a second NPC registry.
* NPC dialogue bindings created by command should default to `managed-entity: false`, because the target entity may be owned by another plugin.

## Open Questions

* None. User confirmed implementation can begin.

## Requirements (evolving)

* Add an `npc-dialogue` entity interaction action.
* Right-clicking an entity with action `npc-dialogue` starts a dialogue sequence.
* Dialogue content is loaded from reviewable YAML config data.
* Dialogue YAML is stored as separate files under the plugin data folder, one dialogue per file, e.g. `dialogues/old-man.yml`.
* Dialogue file schema:
  * `id`: stable dialogue id, matching the filename and interaction `dialogue-id`.
  * `title`: short task/dialogue title.
  * `speaker`: NPC display name used before lines.
  * `opening-lines`: styled lines sent as the opening task/quest block.
  * `lines`: NPC dialogue lines sent sequentially after the opening block.
* MVP formatting supports Minecraft `§` color/style codes in YAML text.
* The interaction entry identifies which dialogue content to use.
* Add `/immortal npc-dialogue set <dialogue-id>` to bind the looked-at entity to a dialogue.
* NPC dialogue bindings created by `set` use action `npc-dialogue` and `managed-entity: false`.
* Add a reload flow so edited YAML dialogue content can be tested without restarting the server.
* Missing dialogue content is logged as a warning and sends no fake/fallback dialogue.
* The opening task/quest-style text is visually distinct from ordinary chat and intentionally tall.
* NPC dialogue lines appear one after another instead of all at once.
* Default NPC line pacing is 30 server ticks, about 1.5 seconds.
* Each NPC line plays a villager sound for the player.
* Villager sound playback uses a slightly varied pitch per line by default, and the YAML schema may expose optional pitch settings for later tuning.
* Successful dialogue start logs a stable `npc_dialogue_started` event.
* Unknown or malformed dialogue content must fail visibly in tests/config validation rather than silently falling back.
* Server cannot know each player's client chat height setting; MVP uses a fixed tall opening block to approximate filling the visible chat area.

## Acceptance Criteria (evolving)

* [x] Java test proves `npc-dialogue` is registered and routed through the existing action router.
* [x] Java test proves `/immortal npc-dialogue set <dialogue-id>` saves a generic entity interaction with `managed-entity: false`.
* [x] Java test proves a configured dialogue renders the opening block and delayed NPC lines in order.
* [x] Java test proves each NPC line triggers a villager sound callback.
* [x] Java test proves NPC line sound pitch varies or follows configured pitch values.
* [x] Java test proves missing dialogue id logs a warning and does not send fallback content.
* [x] Java test proves reload refreshes YAML dialogue content.
* [x] Config/resource test covers the separate dialogue YAML content shape.
* [x] Full main-plugin Gradle build passes.
* [x] Updated plugin jar is deployed and Paper starts.
* [x] Manual server test confirms right-clicking the NPC displays the stylized sequence and plays sounds (confirmed 2026-07-13).

## Definition of Done

* Tests added/updated at the action, presentation, config, and command/resource level where affected.
* Code keeps entity binding/action routing generic.
* No hardcoded NPC listener separate from `ImmortalEntityInteractionListener`.
* No broad `try/catch` or silent fallback.
* Logs go to Paper logs; only intentional dialogue UX goes to player chat.
* Work committed, task archived, journal recorded.

## Out of Scope

* Quest state persistence.
* Dialogue choices/branching.
* GUI dialogue windows.
* Conditions, rewards, objective tracking, or task completion.
* Game Service APIs for quest state.
* MythicMobs/CMI integration.
* NPC/entity creation tooling; this MVP binds to existing looked-at entities, including entities created by other plugins.

## Technical Notes

* Existing plugin assembly: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`.
* Existing generic listener: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/event/ImmortalEntityInteractionListener.java`.
* Existing router interface: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/interaction/EntityInteractionActionRouter.java`.
* Existing first action example: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/gameplay/SpiritRootDetectionInteractionAction.java`.
* Existing config repository reloads disk config via `plugin.reloadConfig()` before loading interactions.
* Chosen command direction:
  * `/immortal npc-dialogue set <dialogue-id>`
  * likely companion commands: `/immortal npc-dialogue list`, `/immortal npc-dialogue remove`, `/immortal npc-dialogue reload`
  * saved interaction action: `npc-dialogue`
  * saved interaction ownership: `managed-entity: false`
* Recommended config direction:
  * `content.entity-interactions.entries[].action: "npc-dialogue"`
  * `content.entity-interactions.entries[].dialogue-id: "<stable id>"`
* Recommended dialogue file direction:
  * data folder path: `dialogues/<dialogue-id>.yml`
  * file-level fields: `id`, `title`, `speaker`, `opening-lines`, `lines`
  * optional file-level fields: `line-delay-ticks`, `sound`, `pitch`
  * example:

```yaml
id: old-man
title: "初入凡尘"
speaker: "老村民"
line-delay-ticks: 30
sound: "entity.villager.ambient"
pitch: 1.0
opening-lines:
  - "§6§l任务开始"
  - "§e初入凡尘"
lines:
  - "年轻人，你身上有一股未定的气。"
  - "去村外的灵石旁看看，也许能照出你的根骨。"
```

## Technical Approach

* Extend `EntityInteractionDefinition` with optional metadata so `npc-dialogue`
  bindings can store `dialogue-id` without creating a dialogue-specific
  binding registry.
* Add an NPC dialogue content repository that reads one YAML file per dialogue
  from `plugins/ImmortalMC/dialogues/<dialogue-id>.yml`.
* Add `NpcDialogueInteractionAction` as a second registered
  `EntityInteractionAction<BukkitEntityInteractionContext>`.
* Add a small presentation scheduler abstraction so unit tests can verify the
  delayed line sequence without a Paper runtime.
* Add `/immortal npc-dialogue set <dialogue-id>`, `list`, `remove`, and
  `reload` for authoring/testing dialogue bindings and reloading YAML content.

## Decision (ADR-lite)

**Context**: NPC dialogue must use the existing generic entity interaction
route while supporting entities owned by other plugins.

**Decision**: Store NPC dialogue bindings as normal `entity-interactions`
entries with action `npc-dialogue`, metadata key `dialogue-id`, and
`managed-entity: false`. Store dialogue content in separate YAML files under
`dialogues/`.

**Consequences**: The Adapter can bind third-party NPC entities without taking
ownership of them. Dialogue content remains editable and reviewable. The MVP
does not persist quest state; later quest logic can call Game Service from the
same action handler pattern.
