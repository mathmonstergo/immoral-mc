# bugfix: spirit root detector target selection

## Goal

Fix `/immortal spirit-root-detector set` so looking at a nearby entity such as a
villager reliably saves that entity as the spirit-root detector binding.

## What I already know

* The user tested while looking at a block or villager and always received:
  "Look at an entity within range before saving a spirit-root detector."
* Binding to blocks is intentionally out of scope for this flow; the command
  should require an entity.
* The current implementation derives the looked-at entity inside
  `ImmortalBukkitCommandExecutor` by checking nearby entities against the
  player's view direction.
* The current selector compares against `entity.getLocation()` which is usually
  near the entity's feet/base, so looking at a villager body/head can miss the
  dot-product threshold.

## Requirements

* `/immortal spirit-root-detector set` must resolve a nearby entity when the
  player is looking at the entity's normal visible body area, not only its base
  point.
* The command must still reject block-only targeting with the existing
  target-missing message.
* The fix must remain independent of CMI/ItemsAdder/MythicMobs.
* The Adapter must continue to save only entity binding identity
  (`world`, `entity-uuid`) and must not add spirit-root gameplay rules.

## Acceptance Criteria

* [ ] A unit test reproduces the previous miss for a villager-height entity
      when the view aims at the entity body/head rather than the base point.
* [ ] The selector chooses the correct nearby entity after the fix.
* [ ] Existing command, detector, and build tests pass.
* [ ] The local Paper server runs the rebuilt plugin on port `25549`.

## Technical Approach

Extract the target selection math into a small testable class. Use entity body
aim points derived from location plus height instead of only the entity base
location. Keep the Bukkit command executor responsible for translating Bukkit
entities into the selector input and `EntityBinding`.

## Out of Scope

* Binding to blocks.
* GUI/wand selection tools.
* Third-party plugin integration.

## Technical Notes

* Primary code path:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/ImmortalBukkitCommandExecutor.java`
* Existing detector admin runner:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/SpiritRootDetectorAdminRunner.java`
* Existing detector entity config:
  `content.spirit-root.detectors`
* Root cause: the original selector compared the player view direction against
  `entity.getLocation()`, which is an entity base point. Villagers and similar
  entities are normally aimed at through their visible body/head area, so the
  base point can miss a strict dot-product threshold.
* Fix: select entities by ray tracing against their bounding boxes and choose
  the nearest hit.
