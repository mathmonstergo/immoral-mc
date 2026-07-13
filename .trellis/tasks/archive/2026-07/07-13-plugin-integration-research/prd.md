# research plugin integration strategy

## Goal

Research Citizens, MythicMobs, and MMOCore in enough technical depth to decide
how each plugin should integrate with ImmortalMC without giving up the custom
quest system, cultivation design, or Game Service authority.

## What I already know

* Paper target is Minecraft 1.21.11 on Java 21.
* Citizens 2.0.43 build 4211 and MythicMobs Premium 5.13.0 dev build are
  installed and start successfully on the local test server.
* MythicMobs reports the current Paper version as supported and enables its
  Citizens integration.
* The user decided that ImmortalMC will implement its own task/quest system.
* Citizens is approved for NPC creation and lifecycle.
* MythicMobs is approved in principle for monsters, AI, and combat presentation.
* An MMOCore 1.13.1 snapshot JAR is available locally but is not installed.
* Game Service must remain authoritative for quest state, combat numbers, loot,
  cultivation, reincarnation, and player progression.
* The user selected the recommended MMOCore approach: do not install MMOCore or
  adopt it as part of the default runtime stack.
* Citizens should replace custom NPC entity/lifecycle concerns, but it does not
  replace ImmortalMC dialogue, interaction routing, or the custom quest system.
* The user approved the recommended migration: keep ImmortalMC dialogue and
  quest logic, and add Citizens as the NPC identity/lifecycle/click adapter.

## Assumptions (temporary)

* Third-party plugins should be optional integrations behind thin Adapter
  boundaries where feasible.
* Plugin-local persistence must not become the only source of cross-system
  gameplay state.
* Research should prefer official documentation, source repositories, API docs,
  and locally inspectable JAR metadata over community summaries.

## Open Questions

* None. The recommendation and migration direction are approved.

## Requirements (evolving)

* Produce separate detailed research notes for Citizens, MythicMobs, and MMOCore.
* Cover capabilities, APIs/events, persistence, dependencies, licensing,
  maintenance/version compatibility, operational risks, and failure modes.
* Map each plugin to current repository modules and authority boundaries.
* Recommend adopt/adapt/reject decisions by subsystem.
* Define a staged integration roadmap with verification checkpoints.
* Do not install MMOCore or add code dependencies during the research task.
* Record MMOCore as rejected for the default runtime stack; no MMOCore PoC is
  currently planned.
* Define the migration boundary between existing ImmortalMC NPC dialogue code
  and Citizens-owned NPC mechanics.

## Acceptance Criteria (evolving)

* [x] Citizens research identifies stable NPC identity and interaction hooks.
* [x] MythicMobs research identifies spawn/combat/death/skill integration hooks.
* [x] MMOCore research identifies reusable and conflicting subsystems.
* [x] Research distinguishes confirmed official facts from assumptions.
* [x] A consolidated recommendation maps plugin responsibilities to ImmortalMC.
* [x] Findings are persisted under `research/` for future implementation tasks.

## Definition of Done

* Research artifacts are complete and source-linked.
* Recommended architecture preserves Game Service authority.
* Risks, licensing constraints, rollout, and rollback are explicit.
* The user can make an informed decision about MMOCore adoption scope.

## Out of Scope

* Implementing Citizens/MythicMobs API adapters.
* Installing or configuring MMOCore on the test server.
* Designing the full quest, combat, or cultivation feature set.
* Purchasing or redistributing commercial plugin artifacts.

## Technical Notes

* Architecture reference: `architecture-v2.md`.
* Plugin boundary spec: `.trellis/spec/backend/quality-guidelines.md`.
* Local JAR staging directory: `plugins-new-add/`.
* Runtime plugin directory: `minecraft-nodes/main-server/plugins/`.

## Research References

* `research/citizens-integration.md`
* `research/mythicmobs-integration.md`
* `research/mmocore-integration.md`
* `research/plugin-integration-recommendation.md`
