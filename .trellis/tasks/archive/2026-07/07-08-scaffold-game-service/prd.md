# Scaffold Game Service

## Goal

Create the first runnable Python FastAPI Game Service scaffold for the Minecraft MMORPG project, so future gameplay slices have a tested backend foundation and a clear place to add module code.

## Requirements

* Create `game-service/` as the backend project root.
* Use Python + FastAPI as defined in `architecture-v2.md`.
* Use the package layout defined in `.trellis/spec/backend/directory-structure.md`.
* Expose a health endpoint that can be called by humans, tests, and future Paper Adapter code.
* Include empty module packages for `player`, `item`, `quest`, `combat`, and `cultivation`.
* Include initial `core/` and `api/v1/` structure.
* Add automated verification commands for formatting/linting and tests.
* Keep the scaffold independent of PostgreSQL, Redis, Paper, and mature Minecraft plugins for this task.

## Acceptance Criteria

* [x] `game-service/pyproject.toml` defines the Python project and dev commands/dependencies.
* [x] `game-service/src/immortal_mmo/main.py` exposes a FastAPI app.
* [x] `GET /health` returns a stable JSON payload with service status.
* [x] FastAPI `/docs` is available when the service runs locally.
* [x] `pytest` verifies the health endpoint.
* [x] `ruff` passes for the scaffold.
* [x] README instructions explain how to install, test, and run the service locally.

## Definition of Done

* Tests added for the scaffold.
* Lint/test commands run and pass, or failures are documented with exact cause.
* Specs updated if the scaffold establishes conventions not already captured.
* Work committed to Git.

## Technical Approach

* Use a `src/` Python package layout: `game-service/src/immortal_mmo/`.
* Keep the initial API minimal: root app plus `api/v1` router and health route.
* Use Pydantic/FastAPI response models for stable API shape.
* Use pytest + FastAPI `TestClient` for initial integration-style endpoint tests.
* Use Ruff for lint/format checking.

## Decision (ADR-lite)

**Context**: The architecture documents already choose Python + FastAPI for Game Service, but the repository has no backend code yet.

**Decision**: Start with a minimal FastAPI scaffold and verification tooling before adding gameplay logic.

**Consequences**: This gives the project a runnable foundation and keeps the first task small. It intentionally delays database schema, Paper Adapter, player account creation, spirit root logic, and server plugin integration to later vertical-slice tasks.

## Out of Scope

* PostgreSQL models, migrations, or database sessions.
* Redis integration.
* Paper Adapter plugin code.
* Account/life creation.
* Spirit root detection.
* Combat, item, quest, cultivation, reincarnation, loot provenance, or technique marks.
* Admin panel UI.
* Docker/deployment automation unless needed for local testing.

## Technical Notes

* `architecture-v2.md` is the authority for Game Service role and Adapter boundaries.
* `game-design-reincarnation-inheritance.md` says single-life character flow comes before account/life split and reincarnation complexity.
* `.trellis/spec/backend/` defines the initial backend conventions for this task.
* User confirmed the architecture/design docs should be treated as known context and not re-asked.
