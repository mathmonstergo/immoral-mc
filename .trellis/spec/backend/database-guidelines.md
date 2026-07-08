# Database Guidelines

> Persistence rules for Game Service state.

## Current Status

The architecture chooses PostgreSQL plus Redis. No ORM or migrations are implemented yet. Initial convention: use SQLAlchemy 2.x style models/sessions and Alembic migrations unless a later ADR replaces them.

## Ownership

PostgreSQL is the source of truth for game state that must survive restarts:

* accounts and lives
* spirit roots, cultivation state, technique progress
* item templates and item instances
* equipment provenance and loot pools
* quest state and rewards
* zone risk-tier snapshots synchronized from Minecraft/WorldGuard configuration

Redis is for ephemeral coordination, cache, queues, pub/sub, or pending events. Do not store authoritative player progression only in Redis.

## Table Boundary Rules

Each module owns its tables. A module may not bypass another module's service layer to read or mutate that module's tables.

Examples:

* `combat` may ask `item` for effective equipment stats; it must not query `item_instances` directly.
* `player` may create a new `life`; `cultivation` may initialize cultivation data through a `player`/`cultivation` service contract, not by hand-editing unrelated tables.
* Reincarnation orchestration may call `item` to migrate droppable equipment into loot pools; it should not duplicate item migration SQL in `player`.

## Core Tables From Current Design

Use this as the starting persistence vocabulary:

```text
accounts
lives
zones
item_templates
item_instances
region_loot_pools
technique_definitions
account_technique_marks
```

`accounts` are permanent and login-linked. `lives` are per-generation character records. Do not collapse them into a single player table once reincarnation work begins.

## Migrations

* Every schema change requires a migration.
* Migrations must be deterministic and reversible when practical.
* Migration filenames should include a short purpose, e.g. `20260708_001_create_accounts_lives.py`.
* Do not edit an applied migration to change behavior. Add a new migration.
* Seed/demo content should be separated from structural migrations unless the schema requires reference rows.

## Query Patterns

* Use repositories for database access. Services call repositories; route handlers do not.
* Use transactions around multi-step state changes such as reincarnation, item migration, quest completion, or breakthrough success.
* Prefer explicit row locks or optimistic version fields for player state changes that can be triggered by rapid player actions.
* Keep deterministic calculations out of SQL when they are gameplay rules. SQL can fetch inputs; services calculate outcomes.
* Avoid N+1 query patterns in loops over inventory, equipment, buffs, or quest states.

## Naming Conventions

* Tables: plural `snake_case`, e.g. `item_instances`
* Primary keys: `<entity>_id`, e.g. `account_id`, `life_id`
* Foreign keys: same name as referenced primary key
* Timestamps: `created_at`, `updated_at`, domain-specific event timestamps such as `died_at`
* Status fields: explicit enums or constrained strings, e.g. `alive`, `reincarnated`
* JSON columns: only for flexible payloads such as rolled stats or provenance entries; do not hide core query fields inside JSON

## Common Mistakes To Avoid

* Treating a Minecraft player UUID as the only player data model. The project needs permanent `accounts` plus per-generation `lives`.
* Letting Paper plugin storage become the cross-system source of truth.
* Storing plugin YAML as the only copy of data that Game Service gameplay rules need.
* Accepting client/plugin-provided result numbers and writing them directly to the database.
* Updating multiple modules' tables from one repository because it looks faster.
