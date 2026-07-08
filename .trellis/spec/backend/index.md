# Backend Development Guidelines

> Initial backend conventions for the Minecraft MMORPG project.

## Scope

These rules apply to the Python FastAPI `game-service/`, database schema and migrations, backend test code, and backend-facing tooling. The Java Paper Adapter is covered here only at the boundary level: it may translate Minecraft events into HTTP requests, but it must not own MMORPG business rules.

This repository currently has architecture documents but no backend implementation. The rules below are initial project conventions inferred from `architecture-v2.md` and `game-design-reincarnation-inheritance.md`. When real code lands, update these files to reference actual examples.

## Pre-Development Checklist

Before editing backend code, read:

1. [Directory Structure](./directory-structure.md)
2. [Database Guidelines](./database-guidelines.md) if persistence, models, repositories, migrations, Redis, or account/life state are touched
3. [Error Handling](./error-handling.md) if API responses, validation, service failures, or adapter-facing contracts are touched
4. [Logging Guidelines](./logging-guidelines.md) if request handling, player lifecycle, combat, item, quest, or cultivation flows are touched
5. [Quality Guidelines](./quality-guidelines.md) before implementation and review
6. Shared guides in `.trellis/spec/guides/`, especially the cross-layer guide for Adapter -> Game Service -> database flows

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Game Service module layout and Adapter boundary | Initial |
| [Database Guidelines](./database-guidelines.md) | PostgreSQL, Redis, repository, and migration rules | Initial |
| [Error Handling](./error-handling.md) | Domain errors and adapter-facing API failures | Initial |
| [Quality Guidelines](./quality-guidelines.md) | Server authority, tests, and review checks | Initial |
| [Logging Guidelines](./logging-guidelines.md) | Structured operational logging | Initial |

## Hard Architecture Rules

* Game Service owns MMORPG rules, calculations, and persistence decisions.
* Paper Adapter reports player actions and presentation events; it does not decide combat damage, cultivation outcomes, loot eligibility, reincarnation, or account progression.
* Game Service is a modular monolith. Modules call each other through explicit service interfaces, not by reaching into another module's tables or repositories.
* Develop by vertical slice. Prefer a thin end-to-end player flow over completing isolated subsystems.
* Tests are part of the feature. At minimum, add formula/data validation tests for deterministic rules and integration tests for player lifecycle flows.
