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

## Schema Bootstrap and Production Migrations

* Before production, Alembic revisions are schema-bootstrap artifacts for a
  fresh database. Rewrite an obsolete development-only revision into the clean
  target shape instead of layering compatibility migrations on top of it.
* After production data exists, every schema change requires a new migration.
* Production migrations must be deterministic and reversible when practical.
* Migration filenames should include a short purpose, e.g. `20260708_001_create_accounts_lives.py`.
* Do not edit a production-applied migration to change behavior. Add a new migration.
* Seed/demo content should be separated from structural migrations unless the schema requires reference rows.

## Scenario: Zero-to-One Schema Replacement

### 1. Scope / Trigger

Trigger: backend, database, API, or configuration design changes before the
server has entered production operation. Development data is disposable and
must not force the target architecture to preserve an obsolete shape.

### 2. Signatures

Development reset and verification commands:

```bash
docker compose down -v
docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/pytest tests/integration/test_migrations.py -q
```

### 3. Contracts

* Design the clean target schema first. Existing development rows, columns,
  payload aliases, and migration history are not compatibility requirements.
* An unapplied or development-only migration may be rewritten when that yields
  the correct target schema. Once production data exists, this rule must be
  replaced by an explicit production migration policy.
* Do not add dual reads, dual writes, legacy columns, endpoint aliases,
  fallback defaults, silent coercion, or background backfills unless a task
  explicitly identifies real data that must survive.
* A stale local database must fail visibly. During zero-to-one development,
  reset and recreate it; runtime code must not detect old shapes and silently
  adapt.
* Reliability mechanisms required by the target design—transactions,
  idempotency, durable outboxes, and retry classification—remain mandatory.
  They protect current correctness and are not legacy compatibility layers.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Local database has an obsolete schema | Readiness fails visibly; developer resets or rebuilds it |
| Old API payload uses removed fields | Typed validation rejects it; service does not translate it silently |
| Old config key is present | Startup/config validation fails unless the current schema defines it |
| Target model changes before production | Rewrite the development migration/schema and update tests directly |
| Durable event is retried | Idempotency returns the stored result; this is correctness, not compatibility |

### 5. Good/Base/Bad Cases

* Good: remove an obsolete column and reset the development database so only
  the final model remains.
* Base: update a development-only Alembic revision, ORM metadata, fixtures,
  and migration assertions in one change.
* Bad: keep `old_value`, `new_value`, and a read fallback because a local test
  database might still contain old rows.
* Bad: accept both old and new request shapes indefinitely during 0-to-1 work.

### 6. Tests Required

* Fresh-schema tests assert the exact head revision, table set, columns,
  constraints, and indexes after `alembic upgrade head` on an empty database.
* Zero-to-one tests do not preserve rows from an obsolete development schema
  and do not require downgrade/re-upgrade compatibility.
* ORM metadata comparison must report no drift from a freshly migrated
  database.
* API/config tests reject removed legacy shapes instead of exercising a
  compatibility branch.

### 7. Wrong vs Correct

#### Wrong

```python
value = row.new_value if row.new_value is not None else row.old_value
```

#### Correct

```python
value = row.value
```

Rebuild disposable development data around the final contract instead of
carrying transitional branches into the server backend.

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

## Scenario: Technique-Backed Cultivation and Mutation Sessions

### 1. Scope / Trigger

Trigger: cultivation, common-technique investment, seclusion, breakthrough,
technique abandonment/transfer, or realm regression changes authoritative life
progress.

### 2. Signatures

```text
life_cultivation_states
life_techniques
technique_investment_entries
life_realm_entries
cultivation_sessions
cultivation_session_techniques
breakthrough_technique_debits
life_item_stacks
item_resource_entries
```

Mutation APIs require `Idempotency-Key: <UUID>`. Session kinds are
`ordinary`, `breakthrough`, and `technique_mutation`.

### 3. Contracts

* Active technique investment is the auditable backing for realized
  cultivation; the state aggregate must equal its sum after every transaction.
* Unrefined cultivation is a separate reserve. Accepted combat rewards add it;
  ordinary seclusion consumes it. Breakthrough and technique loss never do.
* Ordinary seclusion freezes area content, selected technique versions,
  capacity, speed/yield basis points, and full-mastery time.
* At most one pending/active cultivation session exists per life. Lock order is
  account/current life, cultivation state, sorted techniques, then item stack.
* Realm entries are an immutable history. Regression invalidates an active
  suffix; re-entry appends a generation greater than all prior history and
  never revives an invalidated row.
* `technique_mutation` is an explicit completed session shape used to freeze a
  request fingerprint and response for restart-safe replay. It is not disguised
  as ordinary seclusion.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Mixed-major-realm seclusion selection | Reject before session creation |
| More than five or duplicate selections | Reject |
| Mutation while ordinary/breakthrough session is open | Conflict |
| Concurrent session creation wins after the service precheck | Translate the repository race to the same stable conflict; never leak a raw constraint/runtime error |
| Same idempotency key, same request | Return frozen response |
| Same idempotency key, different request | Conflict; no second ledger write |
| Breakthrough item debit is insufficient | Roll back session, debits, item entries, and active-session projection |
| Technique debit invalidates a realm floor | Invalidate suffix and allow cross-major regression |
| Reserve exceeds a lower post-regression cap | Preserve it; block new reward credit until consumed |

### 5. Good/Base/Bad Cases

* Good: item consumption, session creation, technique ledger changes, realized
  aggregate, realm entry changes, and frozen response share one UoW transaction.
* Base: HMAC breakthrough debits are persisted before settlement and replayed,
  never rerolled.
* Bad: store player cultivation independently from technique investment.
* Bad: reactivate an invalidated realm entry or reset unrefined reserve on loss.

### 6. Tests Required

* Fresh migration metadata matches ORM with all named constraints/indexes.
* Partial seclusion settlements equal one combined settlement.
* Ledger sum equals active technique balances and realized aggregate.
* Regression crosses major realms and re-entry uses a new parent/generation.
* Breakthrough start/settle replays across a new app/service instance.
* Fixed entropy yields an exact per-technique debit vector.
* Service tests force both ordinary and breakthrough session-creation races
  and assert stable 409 domain errors with no partial state.
* Item-shortage tests assert the UoW exits without a session, debit, item entry,
  or active-session pointer.

### 7. Wrong vs Correct

#### Wrong

```python
state.realized_cultivation += reward
state.unrefined_cultivation = 0  # on advancement
```

#### Correct

```python
await cultivation.apply_technique_investments(...)
await cultivation.consume_unrefined(...)  # ordinary seclusion only
```

Realized progress changes only with retained technique investment, while the
unrefined reserve keeps its independent mutation boundary.
