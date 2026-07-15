# Database Guidelines

> Persistence rules for Game Service state.

## Current Status

PostgreSQL is implemented as the authoritative persistence store. Redis remains
reserved for future ephemeral coordination and caching; it is not yet a runtime
dependency. The Game Service uses SQLAlchemy 2.x async sessions with asyncpg and Alembic migrations.
`Settings.database_url` is required and must use the
`postgresql+asyncpg://` driver. Production composition has no in-memory
fallback; tests inject explicit fakes or test databases.

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

## Local PostgreSQL and recovery workflow

### 1. Scope / Trigger

The local Compose service and recovery drill are the operator workflow for
development PostgreSQL, migration verification, restart persistence, and dump
restore checks. Compose credentials are disposable development credentials.

### 2. Signatures

* Compose service: `postgres:17-alpine`, published only at
  `127.0.0.1:5432`, with named volume `postgres_data`.
* Required environment: `DATABASE_URL=postgresql+asyncpg://...`.
* Migration commands: `.venv/bin/alembic upgrade head` and
  `.venv/bin/alembic current`.
* Service command: `./scripts/start-game-service.sh`.
* Backup command: `docker compose exec -T postgres pg_dump -U immortal -d immortal -Fc`.

### 3. Contracts

`DATABASE_URL` is required by both production entrypoint settings and the
launcher. Alembic injects this strict URL only when its config does not already
contain an explicit `sqlalchemy.url`, preserving isolated test harnesses.
The launcher installs `.[dev]`, performs no migration, and execs Uvicorn on
`127.0.0.1:8000` using `immortal_mmo.entrypoint:app`.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| `DATABASE_URL` is missing or blank | Launcher exits non-zero before Uvicorn starts |
| URL is not `postgresql+asyncpg://` | Settings/Alembic startup fails visibly |
| PostgreSQL is not ready | Compose healthcheck remains failing; service does not substitute storage |
| New database | Operator runs `alembic upgrade head` explicitly |
| Service restart | Account, life, spirit-root, quest state, and frozen operation responses reload from PostgreSQL |
| Restored database | `alembic current` and the restart smoke run against the isolated URL before reuse |
| Disposable reset | `docker compose down -v` intentionally removes all local data |

### 5. Good/Base/Bad Cases

* Good: copy `.env.example`, export `DATABASE_URL`, bring up Compose, migrate,
  then start the service.
* Base: dump with `pg_dump -Fc`, restore into `immortal_restore`, check the
  Alembic revision, and replay fixed UUID/idempotency keys after restart.
* Bad: publish PostgreSQL on all interfaces, use production credentials in the
  Compose file, run migrations from the service launcher, or fall back to an
  in-memory repository when PostgreSQL is unavailable.

### 6. Tests Required

* Shell syntax check: `bash -n scripts/start-game-service.sh`.
* Alembic CLI integration test: an environment-only `DATABASE_URL` makes
  `.venv/bin/alembic current` report the migration head.
* Migration tests continue to pass when an explicit SQLAlchemy URL is injected
  by the test harness.
* Operational smoke verifies restart persistence, byte-identical idempotency
  replay, custom-format dump, isolated restore, and restored-database replay.

### 7. Wrong vs Correct

#### Wrong

```bash
./scripts/start-game-service.sh  # silently runs without DATABASE_URL
docker compose up -d             # publishes PostgreSQL on every interface
```

#### Correct

```bash
export DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal
docker compose up -d postgres
.venv/bin/alembic upgrade head
./scripts/start-game-service.sh
```

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
