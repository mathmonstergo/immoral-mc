# Scaffold Paper Adapter Plugin

## Goal

Create the first Minecraft-side adapter plugin scaffold under `minecraft-nodes/main-plugin/` so the Paper server can communicate with the existing FastAPI Game Service without putting MMORPG business rules into the plugin.

## Requirements

- Target normal stable Paper `1.21.x`, specifically Paper `1.21.11`.
- Avoid `26.x`, release-candidate, and pre-release Paper lines for this task.
- Use Gradle with Kotlin DSL for the plugin project.
- Pin the Paper API version explicitly instead of using an unbounded latest dependency.
- Use `plugin.yml` rather than the newer experimental Paper plugin manifest.
- Keep the plugin as an adapter only: report Minecraft facts to Game Service and display responses; no cultivation, combat, economy, or player progression rules in Java.
- Include a minimal operator-facing connectivity check command before wiring gameplay events deeply.

## Acceptance Criteria

- [x] `minecraft-nodes/main-plugin/` contains a buildable Paper plugin scaffold.
- [x] The plugin target version is documented and pinned to Paper `1.21.11`.
- [x] `plugin.yml` declares the plugin main class, `api-version`, and first command.
- [x] The initial Java code separates plugin lifecycle, configuration, command handling, and Game Service HTTP access.
- [x] The plugin can check Game Service health without blocking the main server thread.
- [x] Automated checks cover non-Paper business logic where practical.

## Definition of Done

- Tests added or updated where practical.
- Build/lint commands run, or any missing local prerequisites are documented.
- Game Service boundaries remain respected.
- Version choice and local development flow are documented for first-time server development.

## Technical Approach

The plugin will be a thin Paper adapter. The first slice should establish Gradle, the plugin descriptor, configuration for the Game Service base URL, and a small `/immortal health` style command that calls the FastAPI `/health` endpoint asynchronously and reports the result to the command sender.

Player login and spirit-root detection integration should come after the basic plugin can load and talk to Game Service reliably.

## Decision (ADR-lite)

Context: The user wants a normal stable `1.21.x` Paper target, not the newest experimental line.

Decision: Use Paper `1.21.11`, latest checked stable build `132`, as the target for this plugin scaffold.

Consequences: The project gets the newest stable `1.21` API while avoiding `26.x` and pre-release lines. Future upgrades remain localized to `minecraft-nodes/main-plugin/` as long as business logic stays in Game Service.

## Out of Scope

- Running a full local Paper server in this task if JDK/server runtime is not yet installed.
- WorldGuard, MythicMobs, MMOItems, or other mature plugin integrations.
- Player login automation and spirit-root detection command, unless the health-check scaffold is completed first and remains small.
- Database-backed persistence.

## Technical Notes

- Architecture authority: `architecture-v2.md`
- Current backend API: `POST /api/v1/players/login`, `POST /api/v1/players/{account_id}/current-life/spirit-root`, `/health`
- Research reference: `research/paper-version-selection.md`
- Local environment currently has no `java` command, so plugin build verification may require installing a JDK first.
