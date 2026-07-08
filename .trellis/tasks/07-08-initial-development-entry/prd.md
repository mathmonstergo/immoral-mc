# brainstorm: initial development entry

## Goal

Decide the first concrete development slice for the Minecraft MMORPG project and prepare it for implementation without losing the architectural constraints already captured in the project documents.

## What I already know

* The project goal is a long-running MMORPG server using Minecraft as the client/presentation layer, not a conventional all-in-one Minecraft plugin server.
* The current architecture target is a modular monolith Game Service in Python + FastAPI, with a Java Paper Adapter Plugin translating Minecraft events into local HTTP calls.
* Current repository content is documentation and Trellis scaffolding only; no `game-service/`, `minecraft-nodes/`, database, or test code exists yet.
* Top-level design documents are `architecture-v2.md` and `game-design-reincarnation-inheritance.md`.
* Trellis backend/frontend spec files currently exist but are still template placeholders.
* There is an active Trellis bootstrap task, `00-bootstrap-guidelines`, intended to populate `.trellis/spec/` with real project conventions.
* The local `.git/` directory exists but is empty/incomplete; `git status` currently fails with `fatal: not a git repository`.

## Assumptions (temporary)

* The first implementation should follow the documented vertical-slice strategy rather than building complete subsystems in isolation.
* The safest first slice is the "single-life character loop" before introducing reincarnation complexity.
* Because no code exists yet, the first implementation may need to create the initial project scaffold, package layout, and verification commands.
* FastAPI, PostgreSQL, and Redis are the intended backend direction from the architecture document, but the exact local development stack still needs confirmation.

## Open Questions

* None for the current decision. The developer chose to fill Trellis specs before writing the first gameplay slice.

## Requirements (evolving)

* First development target: fill `.trellis/spec/` so future implementation sessions have concrete project conventions.
* Preserve the architecture boundary: Paper Adapter handles Minecraft integration; Game Service owns MMORPG rules and persistence decisions.
* Keep combat and progression server-authoritative: Adapter reports player actions, not trusted result numbers.
* Develop by vertical slice and include tests appropriate to the slice.
* Do not introduce mature Paper plugins before the slice first needs them.

## Acceptance Criteria (evolving)

* [x] A first MVP development target is chosen: fill Trellis backend/frontend specs first.
* [x] PRD scope clearly states what is in and out of scope.
* [ ] The existing `00-bootstrap-guidelines` task updates backend and frontend spec files from placeholders into project-specific initial conventions.
* [ ] Future implementation approach can use these specs when creating the first Game Service slice.

## Definition of Done (team quality bar)

* Tests added/updated where appropriate.
* Lint/typecheck or equivalent quality commands are defined and pass.
* Docs/spec notes updated if the implementation establishes new project conventions.
* Rollout/rollback considered if the change affects persistence or server state.

## Out of Scope (explicit)

* Multi-server / Velocity deployment.
* Full reincarnation, provenance loot pools, and technique marks unless chosen as the first MVP.
* Admin content editor UI.
* MCDR operational automation.
* Deep integration with MythicMobs, MMOItems, MMOCore, BetonQuest, or economy plugins before the relevant vertical-slice step needs them.

## Technical Notes

* 2026-07-08 decision: developer selected option 2, "fill Trellis spec docs first".
* The actual work should continue under `.trellis/tasks/00-bootstrap-guidelines`, which already exists for this purpose.
* `architecture-v2.md` says the current target is a single Paper world, Java Adapter Plugin, local HTTP, and Python FastAPI Game Service.
* `architecture-v2.md` recommends the first vertical slice: enter game -> spirit root check -> join sect -> learn technique -> kill monster -> gain resource -> breakthrough -> save data.
* `game-design-reincarnation-inheritance.md` recommends implementation phases:
  1. Single-life character loop without reincarnation.
  2. Account/life split.
  3. Death zones and reincarnation trigger.
  4. Equipment provenance and loot pool.
  5. Technique marks.
* `.trellis/spec/backend/index.md` and `.trellis/spec/frontend/index.md` are placeholders; guidelines should be filled once real conventions exist or during bootstrap.
* The repository should be initialized or repaired as a Git repository before substantial development so work can be tracked safely.
