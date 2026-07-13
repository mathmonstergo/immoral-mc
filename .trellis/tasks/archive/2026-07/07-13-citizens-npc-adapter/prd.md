# Citizens NPC adapter

## Goal

Integrate Citizens as the persistent NPC identity, lifecycle, and click layer
without replacing the existing ImmortalMC dialogue presenter, interaction
router, or future Game Service-authoritative quest system.

## What I already know

* The user approved Citizens for NPC mechanics and rejected MMOCore from the
  default stack.
* Citizens 2.0.43 build 4211 is installed and verified on Paper 1.21.11 / Java 21.
* Existing NPC dialogue playback has passed manual server verification.
* Existing bindings use `world + Bukkit entity UUID`.
* Citizens durable identity is `NPC#getUniqueId()`.
* Citizens right-click integration should use `NPCRightClickEvent`.
* Existing generic Bukkit interaction routing must continue to support
  non-Citizens entities such as spirit-root detectors.

## Requirements

* Add Citizens as an optional `compileOnly` integration and `softdepend`.
* Persist Citizens-backed dialogue bindings with provider and persistent NPC UUID metadata.
* Keep the legacy world/entity binding fields readable for existing interactions.
* Route Citizens right-clicks through the existing action router exactly once.
* Skip Citizens entities in the generic Bukkit entity interaction listener.
* Adapt `/immortal npc-dialogue set/remove` to prefer the persistent Citizens UUID.
* Rebinding the same Citizens NPC must replace its previous dialogue binding.
* Rapid duplicate Citizens click delivery must not start duplicate dialogue sessions.
* ImmortalMC must still enable when Citizens is absent.
* Do not move dialogue content, task state, rewards, or cultivation rules into Citizens.
* The 500ms click debounce filters duplicate/rapid event delivery only. Dialogue
  session re-entry and repeatability are controlled by future dialogue/quest state.

## Acceptance Criteria

* [x] Unit test proves a Citizens UUID binding survives a changed Bukkit entity binding.
* [x] Unit test proves Citizens click routing invokes one configured action.
* [x] Unit test proves rapid duplicate click routing is suppressed.
* [x] Unit test proves admin set/remove uses persistent Citizens UUID metadata.
* [x] Unit test proves legacy non-Citizens bindings still load and route.
* [x] Unit test proves generic listener exclusion is driven by the optional resolver.
* [x] Full offline Gradle test/build passes.
* [x] Paper starts with Citizens and ImmortalMC enabled without severe errors.
* [x] Manual restart verification proves the Citizens NPC dialogue still works.

## Out of Scope

* Creating the full quest state system.
* Citizens skins, navigation, patrol, shops, or custom traits.
* MythicMobs combat integration.
* Automatic conversion of every legacy Bukkit entity binding.
* Preventing a player from deliberately restarting a dialogue after the click
  debounce window; that belongs to dialogue-session and quest-state policy.

## Technical Approach

* Keep `EntityInteractionDefinition` backward compatible and store Citizens
  identity as explicit metadata keys.
* Add registry lookup/removal by metadata so the persistent Citizens UUID is
  authoritative even if the spawned Bukkit entity UUID changes.
* Isolate Citizens API types under a dedicated optional integration package.
* Expose a Citizens-free resolver interface to command and generic listener code.
* Use a short monotonic-time debounce at the Citizens event boundary.

## Research References

* `.trellis/tasks/archive/2026-07/07-13-plugin-integration-research/research/citizens-integration.md`
* `.trellis/tasks/archive/2026-07/07-13-plugin-integration-research/research/plugin-integration-recommendation.md`
