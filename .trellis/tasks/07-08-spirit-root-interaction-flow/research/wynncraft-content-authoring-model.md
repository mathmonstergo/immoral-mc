# Wynncraft Content Authoring Model Research

## Scope

The question: is Wynncraft fully self-developed, or does it combine custom code
with editable content tooling and existing Minecraft tools?

Wynncraft is proprietary, so exact server internals and plugin lists are not
public. This note separates public facts from engineering inferences.

## Sources Checked

* Wynncraft official site: `https://wynncraft.com/`
* Wynncraft official API docs/OpenAPI:
  * `https://docs.wynncraft.com/welcome`
  * `https://docs.wynncraft.com/openapi.json`
* Official Wynncraft Wiki:
  * `https://wynncraft.wiki.gg/wiki/Wynncraft`
  * `https://wynncraft.wiki.gg/wiki/Content_Team`
  * `https://wynncraft.wiki.gg/wiki/Newcomer%27s_Guide`

## Public Facts

### Player-facing product

The official site describes Wynncraft as "The Minecraft MMORPG" and says no
mods are required to play. It advertises classes/abilities, quests, roleplay,
loot/economy, raids, bosses, guild territories, and a large handcrafted map.

The official site also says builds and landscapes are created by their build
team over many years, and that "No external tools are used to generate
landscapes and builds" in the sense of procedural generation. That does not
mean builders use no editing tools; the Content Team page confirms they do.

The Newcomer's Guide says the official resource pack automatically downloads
when joining a world, and that it is effectively required because the game can
crash or not display correctly without it. It also states the game has over
4500 items and uses the resource pack for weapon models.

### Team structure

The official wiki's Content Team page states:

* The Content Team adds buildings, quests, mobs, items, music, and art.
* Developers handle the technical side: coding, in-game features, website, and
  infrastructure.
* Game Masters create playable content and work with YAML `.yml` files plus
  Wynncraft's proprietary scripting language.
* Game Masters use that workflow for quests, discoveries, minigames, events,
  lootrun challenges, mobs, and more.
* Scripters use a unique domain-specific language called WynnScript for dynamic
  features and libraries for GMs/Scripters.
* Builders use plugins such as WorldEdit and VoxelSniper.
* Item Makers create and balance items and IDs, including Major IDs, in a
  workflow similar to Game Masters.
* Modelers historically used a proprietary armor stand editing plugin for
  complex resource-pack model assemblies and animation, while resource-pack
  modelers use Blockbench for custom mobs, weapon models, and cosmetics.
* Artists create GUI art, particle effects, skins, and resource pack work.

### Public API surface

The official API docs expose a structured data model. Public endpoints include:

* Online players and player profiles.
* Character data and ability maps.
* Item database/search, item sets, recipes, and item metadata.
* Class details and ability trees.
* Map markers, raids, camps, loot pools, gathering nodes, quests, world events,
  and visible player locations.
* Guilds, territories, seasons, and leaderboards.

OpenAPI schemas show structured properties for characters, items, ability
trees, and map markers. For example:

* Character data includes level, XP, skill points, professions, dungeons,
  raids, world events, lootruns, caves, quests, mobs killed, chests found, and
  content completion.
* Item data includes internal/display names, types, icons, tiers, attack speed,
  DPS, restrictions, elements, requirements, major IDs, powder slots, lore,
  identifications, and base stats.
* Map markers expose coordinates and icons.

This strongly suggests a deliberate data/content model behind the server, not
ad hoc command chains.

## Engineering Inferences

These are reasonable inferences, not confirmed internals:

* Wynncraft likely has a substantial custom server codebase for core gameplay,
  persistence, APIs, character progression, abilities, combat rules, market,
  map sync, and multi-server infrastructure.
* Content is likely mostly data/script driven, authored by specialized content
  roles rather than by Java developers for every quest/mob/item.
* Their production model resembles an internal game engine:
  * developers build engine features and authoring tools,
  * GMs/Scripters/Item Makers/Builders/Artists create content,
  * YAML, proprietary scripting, resource packs, and editing plugins bridge the
    two.
* They use existing ecosystem tools where those tools fit: WorldEdit,
  VoxelSniper, Blockbench, and likely resource-pack pipelines. They do not need
  to reinvent every editor.

## What This Means For ImmortalMC

The right target is not "copy Wynncraft's code" or "buy enough plugins to avoid
coding". The right target is a smaller version of the same separation:

* Build a custom ImmortalMC gameplay engine for the xianxia/MMORPG rules:
  account/life state, spirit roots, cultivation, combat progression, rewards,
  persistence, logs, and Game Service authority.
* Make content data-driven:
  monsters, interactions, items, rewards, conditions, triggers, cooldowns,
  messages, sound/particle effects, region bindings, and plugin content IDs.
* Provide in-game authoring tools:
  commands, GUI flows, or selection/wand-style tools that write versionable
  YAML/JSON definitions.
* Use mature plugins where they are strong:
  * WorldEdit/FastAsyncWorldEdit or similar for world building.
  * ItemsAdder for resource-pack backed custom items, blocks, furniture, HUDs,
    sounds, and models.
  * MythicMobs for mob/skill/boss authoring when its model matches our needs.
  * CMI for server administration, convenience commands, portals/holograms, or
    prototypes, not as the source of truth for cultivation rules.

## Recommendation

For ImmortalMC, use an "engine + content + editor + adapters" architecture:

1. Engine capabilities in code:
   `spirit_root_detection`, `grant_cultivation_exp`, `spawn_content_mob`,
   `grant_item`, `start_dialogue`, `open_trade`, etc.
2. Content definitions in YAML/JSON:
   trigger, binding, conditions, actions, presentation, and references to
   ItemsAdder/MythicMobs/CMI IDs.
3. In-game authoring:
   admin commands and later GUI/wand flows that create/update those content
   files from the server.
4. Optional plugin adapters:
   small integration modules that translate external plugin events/content into
   ImmortalMC trigger/action contracts.

For the current spirit-root work, this means the altar should be the first
content definition plus authoring workflow, not a one-off command or hardcoded
listener.
