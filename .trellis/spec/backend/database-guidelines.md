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

### Current project decision (development-only schema changes)

ImmortalMC is still in disposable development. When a gameplay model changes,
the clean target is written directly into the development migration/ORM/tests,
the local PostgreSQL volume is deleted and recreated, and old rows/sessions are
not preserved. Do not add compatibility revisions, legacy snapshot readers,
dual formulas, downgrade guards, or data backfills solely to protect local
development data. A future production release will establish a separate
migration policy once real player data exists.

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

Ordinary sessions freeze this JSON shape in `cultivation_sessions.frozen_snapshot`:

```text
area_version
cycle_seconds = 10
technique_group
technique_capacity
full_mastery_seconds
base_cultivation_per_cycle
player_major_realm / player_speed_weight
technique_major_realm / technique_speed_weight
speed_basis_points / yield_basis_points
cultivation_per_cycle
```

### 3. Contracts

* A new life starts at realm level `0` (`凡人`). The authoritative realm range
  is `0..22`; ordinary qi settlement enters level `1` after 50 retained points
  and appends an immutable `0 -> 1` adjacent realm entry in the same
  transaction. Levels `1..22` retain their existing IDs and per-level
  `max_exp` values.
* Active technique investment is the auditable backing for realized
  cultivation; the state aggregate must equal its sum after every transaction.
* Unrefined cultivation is a separate reserve. Accepted combat rewards add it;
  ordinary seclusion consumes it. Breakthrough and technique loss never do.
* Ordinary seclusion selects one to five active, non-mastered techniques with
  exactly one `group_code` and one capacity. Selection count never increases
  the session's total speed.
* A cycle is ten seconds. Base speed is
  `max(1, floor(capacity * 10 / full_mastery_seconds))`; final speed is
  `max(1, floor(base * player_speed_weight * speed_basis_points /
  technique_speed_weight / 10000))` and is frozen at session start.
* Major-realm speed weights are mortal/qi/foundation/core/nascent =
  `1/1/2/5/10`.
  They change elapsed-time speed only. Technique layer-growth ratios such as
  `3:2` or `17:10` never participate in seclusion speed and capacities/costs
  are never multiplied by the speed ratio.
* `completes_at` for an ordinary session is `started_at + 10 seconds`, the
  first settlement boundary rather than an estimated mastery timestamp.
  Cumulative generated cultivation is `floor(elapsed_seconds / 10) *
  cultivation_per_cycle`.
* Yield conversion and equal technique allocation are calculated from the
  session's cumulative generated/consumed/retained targets, then only the
  difference from persisted totals is written. Never round or allocate only
  the latest increment: split and combined settlement must be identical per
  technique as well as in aggregate.
* For cumulative retained cap `C` and yield `Y`, required reserve is
  `ceil(C * 10000 / Y)`. Consume at most that cumulative amount and clamp
  `floor(consumed * Y / 10000)` to `C`. Preventing raw retained from crossing
  `C` instead will permanently strand the last capacity points when `Y > 10000`.
* A full current-realm progress bar ends a session only when the selected
  technique group is the current progress group. A high-realm player training
  a lower-realm technique is not stopped by the unrelated high-realm barrier.
* At most one pending/active cultivation session exists per life. Lock order is
  account/current life, cultivation state, sorted techniques, then item stack.
* Realm entries are an immutable history. Regression invalidates an active
  suffix; re-entry appends a generation greater than all prior history and
  never revives an invalidated row.
* Every valid active realm chain starts with an active `0 -> 1` root whose
  `parent_entry_id` is null. Every later row points to the previous active row,
  and its `source_level` equals that parent's `target_level`. The database
  enforces the root shape; projection rejects missing, disconnected, or
  group-inconsistent chains instead of treating them as partial history.
* Same-group re-entry advances to the adjacent level and projects progress from
  the entry's cumulative `target_baseline`. Cross-group re-entry projects from
  zero so retained investment already present in the restored target group is
  visible. Both cases append a new generation and never reactivate history.
* `technique_mutation` is an explicit completed session shape used to freeze a
  request fingerprint and response for restart-safe replay. It is not disguised
  as ordinary seclusion.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Mixed group, capacity, or major-realm seclusion selection | Reject before session creation |
| More than five or duplicate selections | Reject |
| Settlement before the first complete ten-second cycle | Stable `cultivation.seclusion_conflict`; no mutation |
| Old session snapshot lacks required cycle keys | Fail visibly; do not read an old formula or supply fallback values |
| High-realm player trains a lower-realm technique while the current bar is full | Keep the session active until the selected techniques master or their own group barrier applies |
| Mutation while ordinary/breakthrough session is open | Conflict |
| Concurrent session creation wins after the service precheck | Translate the repository race to the same stable conflict; never leak a raw constraint/runtime error |
| Same idempotency key, same request | Return frozen response |
| Same idempotency key, different request | Conflict; no second ledger write |
| Breakthrough item debit is insufficient | Roll back session, debits, item entries, and active-session projection |
| Technique debit invalidates a realm floor | Invalidate suffix and allow cross-major regression |
| Reserve exceeds a lower post-regression cap | Preserve it; block new reward credit until consumed |
| Realm history lacks `0 -> 1`, skips a source/target level, or has an invalid parent | Stop the active-chain projection at the first invalid row; do not infer compatibility history |

### 5. Good/Base/Bad Cases

* Good: item consumption, session creation, technique ledger changes, realized
  aggregate, realm entry changes, and frozen response share one UoW transaction.
* Good: recompute cumulative yield and water-fill allocation, then persist only
  positive deltas for this settlement.
* Base: HMAC breakthrough debits are persisted before settlement and replayed,
  never rerolled.
* Bad: multiply technique capacity or layer costs by the player's realm weight.
* Bad: round yield and call `allocate_equal()` independently for every partial
  settlement; integer remainders make split results diverge.
* Bad: store player cultivation independently from technique investment.
* Bad: reactivate an invalidated realm entry or reset unrefined reserve on loss.

### 6. Tests Required

* Fresh migration metadata matches ORM with all named constraints/indexes.
* Formula tests lock 9/10/25-second boundaries, same-realm `1x`, foundation-to-qi
  `2x`, nascent-to-foundation `5x`, nascent-to-core `2x`, and area speed.
* Service tests compare one combined settlement with multiple partial
  settlements for every selected technique and for non-integral yield such as
  `15000` basis points.
* Start tests assert one/five selections freeze the same total speed, mixed
  group/capacity selections fail, and the complete frozen JSON shape persists.
* Ledger sum equals active technique balances and realized aggregate.
* A real PostgreSQL API/UoW test settles a mortal ordinary session and asserts
  the state, technique investment, resource ledgers, session totals, and
  `0 -> 1` realm entry commit together.
* Regression crosses major realms and re-entry uses a new parent/generation.
* Active-chain tests reject a missing `0 -> 1` root and disconnected levels;
  projection tests distinguish same-group cumulative baselines from cross-group
  retained-investment restoration.
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

#### Wrong

```python
retained = incremental_consumed * yield_basis_points // 10_000
allocations = allocate_equal(retained, current_remaining)
```

#### Correct

```python
required = ceil(cumulative_retained_cap * 10_000 / yield_basis_points)
target_cumulative_consumed = min(total_available_reserve, required)
target_retained = min(
    target_cumulative_consumed * yield_basis_points // 10_000,
    cumulative_retained_cap,
)
target_allocations = allocate_equal(target_retained, frozen_initial_remaining)
changes = target_allocations - allocations_already_written_by_this_session
```

The cumulative target preserves integer remainders and deterministic UUID
tie-breaking across retries, offline catch-up, and partial settlement.

## Scenario: Quest Objective Progress and Item Delivery Persistence

### 1. Scope / Trigger

Trigger: adding typed quest objectives, durable post-acceptance event counters,
or atomic item delivery to the PostgreSQL-backed quest flow.

### 2. Signatures

```text
quest_objective_progress(
  life_id, quest_id, objective_id, definition_version,
  objective_type, target_id, required_value, current_value, updated_at
)
```

Physical delivery uses `item_instances` with stable `item_instance_id`, status,
and location. Logical `life_item_stacks` remain for quantity resources such as
breakthrough pills; quest delivery must not add a second stack-debit path.

```text
life_inventory_states(life_id primary key, revision >= 0)
```

### 3. Contracts

* Only MythicMobs event objectives have durable progress rows. Rows are created
  with zero at quest acceptance and may only increase up to `required_value`.
* A rewardable combat fact requires a non-null `source_life_id` that matches
  the locked current life. Missing or stale source-life facts become terminal
  `current_life_unavailable` events and are never rebound to a new life by a
  delayed outbox delivery.
* Combat-to-quest progression locks the per-life quest revision row before it
  reads accepted progress or objective rows. This serializes a kill with
  accept/turn-in so a concurrently accepted quest cannot permanently miss the
  already-committed combat event.
* A combat transaction inserts the event, advances all matching active rows in
  one bounded update, updates the lifetime counter/reward, and commits once.
* Turn-in receives the unique item-instance IDs observed in the Paper player
  inventory. Game Service locks those rows, verifies current-life ownership,
  `status=owned`, `location=inventory`, and exact `item_code`, selects every
  required instance, consumes them, and completes the quest in one transaction.
  A later shortage or identity mismatch leaves every instance owned.
* `life_inventory_states.revision` is the monotonic per-life input revision for
  physical item objectives. Increment it in the same transaction whenever an
  item enters, leaves, or is consumed from `owned/inventory`; pending delivery
  creation alone is not inventory input. Projection reads must retry a bounded
  stable read or re-read under the revision-row lock.
* Reward persistence is parent-first inside the shared Unit of Work. Flush
  `quest_reward_grants` before quest-backed `item_instances`, and flush
  `quest_cultivation_reward_grants` before its cultivation ledger entry.
  SQLAlchemy mapper ordering must not be assumed to infer raw foreign-key
  dependencies when no ORM relationship is declared. These flushes establish
  insert order only; the final commit remains atomic.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Objective progress identity/definition differs | Stable conflict; transaction rolls back |
| Counter would exceed required value | Bounded at required value |
| Kill races with quest acceptance | Wait on the quest revision lock, then count when `occurred_at >= accepted_at` |
| Rewardable combat fact has no matching source life | `current_life_unavailable`; no reward, lifetime counter, or quest progress |
| Presented item ID is duplicated, missing, stored, consumed, or belongs to another life | `quest.not_ready` or stable conflict; no instance is consumed |
| One delivery type is insufficient | No instance is consumed and the quest remains active |
| Inventory quantity decreases or an equal-count instance is replaced | Inventory revision increases; a newer projection may contain lower progress |
| Same quest operation key and request | Frozen response replay; no second reward or consumption |
| Same quest operation key with different inventory identities | `quest.idempotency_conflict`; no mutation |
| Child reward row is attempted before its grant parent | Treat as an implementation defect; never retry around the foreign-key failure |

### 5. Good/Base/Bad Cases

* Good: repositories own only their module tables; the shared Unit of Work
  coordinates combat, quest, cultivation, and item changes.
* Base: Paper scans physical identities; Game Service independently validates
  every identity and chooses the exact instances to consume.
* Bad: debit `life_item_stacks` for quest delivery, trust display names/Lore,
  or consume one item before validating the rest.

### 6. Tests Required

* Fresh migration metadata checks table fields, constraints, trigger, index,
  and head revision.
* PostgreSQL tests cover bounded bulk increments, duplicate/replayed events,
  physical-instance ownership/location validation, multi-item shortage rollback,
  exact consumed IDs, inventory revision on removal/same-count replacement,
  parent-before-child item/cultivation reward issuance, and restart reads.
* Real PostgreSQL concurrency tests prove accept-versus-kill serialization and
  stable quest-operation replay under concurrent delivery.
* Fresh migration smoke checks exact metadata at head; disposable development
  data is reset instead of backfilled or protected by downgrade guards.

### 7. Wrong vs Correct

#### Wrong

```python
if existing_entry_for(operation_id, item_code):
    return existing_entry
```

#### Correct

```python
if existing_entry.identity != requested_identity:
    raise ItemOperationConflict
return existing_entry
```

#### Wrong

```python
await items.create_pending_instances(quest_reward_grant_id=grant_id)
await quests.insert_reward_grant(grant)
```

#### Correct

```python
await quests.insert_reward_grant(grant)  # flushes the parent
await items.create_pending_instances(quest_reward_grant_id=grant_id)
await uow.commit()  # both remain one atomic transaction
```

## Scenario: Physical Item Issuance and Regional Storage

### 1. Scope / Trigger

Trigger: a quest, loot, crafting, delivery, technique manual, or regional
warehouse flow creates or moves a stable physical item instance.

### 2. Signatures

```text
item_instances(
  item_instance_id, life_id, issuance_id, issuance_ordinal,
  quest_reward_grant_id?, item_code, definition_version, technique_id?,
  status, location?, delivered_at?, consumed_at?
)
regional_storage_containers(life_id, area_id, page_count,
                            item_slots_per_page, revision)
regional_storage_slots(life_id, area_id, page, slot, item_instance_id)
regional_storage_operations(operation_id, life_id, area_id, move_kind,
                            expected_revision, resulting_revision,
                            request_fingerprint, response_body)
```

Mutation APIs require UUID `Idempotency-Key`; storage moves also carry
`expected_revision` and exact source/destination coordinates.

### 3. Contracts

* `issuance_id + issuance_ordinal` is the generic creation identity. A nullable
  `quest_reward_grant_id` records quest provenance without making every item a
  quest item. Do not add required source-specific columns for loot or crafting.
* Item state is one exact shape: `pending_delivery` has no location,
  `owned` has `inventory` or `storage`, and `consumed` has no location.
* Quest turn-in consumes only explicitly presented, current-life,
  `owned/inventory` instances. Logical stacks are not a compatibility path.
* Regional storage is current-life plus stable `area_id`; Paper coordinates
  never become the database key.
* Every storage operation acquires the operation UUID advisory transaction
  lock before reading replay history. The container row then serializes its
  revision, and slot rows are locked in deterministic coordinate order.
* A successful move updates item location, slot rows, container revision, and
  frozen operation response in one Unit of Work. An occupied destination is an
  atomic swap.
* Fresh development databases migrate directly to the target schema. Do not
  retain `grant_id`-only item identity, dual reads, backfills, or downgrade
  guards for disposable local data.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Same issuance identity repeats | Return/reuse the same logical issuance; never create a second instance |
| Same operation UUID and fingerprint repeats | Return the frozen response |
| Same operation UUID with different account/area/request | Stable idempotency conflict |
| Expected storage revision is stale | Stable revision conflict; no slot or location mutation |
| Slot references a missing or non-`owned/storage` item | Fail visibly as an invariant violation |
| Deposit item is not `owned/inventory` | Reject; do not create a slot |
| Withdraw target inventory is full on Paper | Do not submit, or reconcile after uncertainty; storage remains authoritative |

### 5. Good/Base/Bad Cases

* Good: task reward creates a pending manual, Paper confirms delivery, storage
  changes its location, withdrawal restores it, and learning consumes the same
  instance ID.
* Base: two items in one page exchange slots with one revision increment.
* Bad: copy an ItemStack by display name, store inventory in plugin YAML, or
  catch a uniqueness race and report success without replay validation.

### 6. Tests Required

* Fresh migration/ORM metadata asserts all columns, named constraints, indexes,
  foreign keys, and the single Alembic head.
* Unit tests cover issuance replay, delivery confirmation, manual consumption,
  area isolation, pagination, stale revision, move, swap, withdrawal, and
  snapshot invariant rejection.
* PostgreSQL tests cover full reward-manual storage round trip and prove a
  competing identical operation waits on an advisory lock.
* Adapter tests assert exact snake-case HTTP payloads, stable manual operation
  UUID derivation, reconciliation deduplication, and strict DTO state shapes.

### 7. Wrong vs Correct

#### Wrong

```text
quest reward -> Paper gives named book -> local chest YAML -> trust GUI contents
```

#### Correct

```text
Game Service issuance -> item_instance_id -> Paper projection
-> revisioned Game Service storage move -> authoritative reconciliation
```
