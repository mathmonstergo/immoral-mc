# brainstorm: Minecraft PostgreSQL schema design

## Goal

Design the PostgreSQL schema for the Minecraft Game Service by using
`/home/adam/projects/mortals/init_db.py` as domain reference material without
copying its QQ-bot storage model wholesale. The first implementation target is
durable account/current-life/spirit-root/quest state; the schema should leave a
clear path for cultivation, items, combat, reincarnation, and social systems.

## What I already know

* The Minecraft architecture separates permanent `accounts` from per-generation
  `lives`; PostgreSQL is the authoritative store for progression.
* The current Game Service uses `InMemoryPlayerRepository` and
  `InMemoryQuestRepository`; state is lost on process restart.
* Current player state includes Minecraft UUID/player name, current life,
  generation/status, spirit-root quality/elements, and revision values.
* Current quest state requires `(life_id, quest_id)` uniqueness, definition
  versioning, quest revisions, and an idempotency ledger for accept/turn-in.
* The previous QQ bot schema contains useful domain vocabulary: realm/cultivation,
  spirit roots, lifespan, karma, sects, items/equipment, reincarnation history,
  gongfa, markets, teams, dungeons, and PVP. It also mixes current state,
  presentation labels, temporary runtime state, and future systems in one
  `players` table.
* Most columns in the QQ bot `players` table are conceptually per-life character
  state rather than permanent account state. The MC design must retain that
  breadth over time, but split it into module-owned tables keyed by `life_id`
  instead of recreating one oversized `lives` row.
* The MC schema must keep module ownership boundaries: player, cultivation,
  quest, item, combat, and future social systems own their tables and services.

## Assumptions

* The first migration should persist only the current playable vertical slice,
  not every table from the old bot.
* PostgreSQL access will follow the repository/service boundary and the project
  convention of SQLAlchemy 2.x plus Alembic, unless design discussion changes
  that decision.
* Flexible JSONB is appropriate for opaque snapshots or future payloads, but
  query-critical fields remain typed columns.

## Requirements

* Preserve permanent account identity separately from per-life state.
* First migration scope is the core vertical slice only: accounts, lives,
  spirit-root state, quest progress, and quest operation idempotency.
* A life receives exactly one immutable spirit-root assignment. It remains
  unchanged for the lifetime of that life and is not replaced by detection,
  retry, or ordinary gameplay actions. A new generation receives a new
  assignment after the previous life is judged dead.
* Spirit-root identity, quality, and elements are immutable birth facts. A
  future cultivation migration may add versioned immutable base numeric
  snapshots once their semantics are implemented. Items, pills, techniques,
  statuses, and temporary buffs modify effective values through separate
  life-scoped effect/adjustment records; they never overwrite the original root.
* Cultivation effects reserve three explicit lifetimes:
  `permanent_life`, `timed`, and `next_action`. Content may use only the scopes
  it needs, but persistence and service contracts must not collapse them into a
  single mutable buff JSON column.
* Spirit-root element vocabulary is intentionally small and stable. Keep the
  definitions in version-controlled code, persist stable English element codes,
  derive localized labels in the application, and enforce allowed codes with
  database constraints. Do not add an element catalog table in this slice.
* Store the fixed base-element set compactly on the one-to-one spirit-root row;
  adding a rare new element requires an application release plus a migration
  that updates the database constraint.
* Quest definitions remain code/version-control-owned for this phase. PostgreSQL
  stores player progress and the definition version observed by each progress
  row, without a foreign key to a future content database. A later content
  authoring system can introduce versioned definition tables independently.
* The MC database starts clean with Minecraft UUID identity. It contains no
  `legacy_user_id` or permanent compatibility columns for the QQ bot schema.
  Any future data import is an explicit one-off SQL/ETL operation outside the
  core runtime model.
* Accounts retain both a last-known Minecraft name and first/last-seen name
  observations in `account_minecraft_names`. Names are display/audit data, never identity;
  historical names are not globally unique because Minecraft names can be
  reused.
* `quest_operations` is a compact technical idempotency ledger, not a player
  history/analytics archive. In the first PostgreSQL implementation, the
  operation insert, quest mutation, revision increment, and frozen response are
  committed in one short transaction. A crash rolls back the whole transaction,
  so leases, worker ownership, mutation recovery snapshots, and a separate
  operation archive table are unnecessary.
* Quest objective progress is not stored as a second mutable truth source. A
  quest projection loads current-life facts, persisted `quest_progress` rows,
  and version-controlled quest definitions, then derives each quest state
  (`unavailable`, `available`, `active`, `ready_to_turn_in`, `completed`).
  Future objective types must implement an evaluator/service contract against
  their authoritative module rather than writing duplicate counters here.
* Ordinary Minecraft deaths do not end a life. Only a Game Service decision that
  triggers reincarnation closes the current life, records terminal death fields,
  and permits creation of the next generation.
* `lives.status` uses the terminal transition `alive -> reincarnated`. Database
  constraints require terminal timestamps for reincarnated lives and permit at
  most one `alive` life per account through a partial unique index.
* Make restart-safe login, spirit-root detection, quest accept, and quest turn-in
  possible with transactional repository methods.
* Enforce life/quest uniqueness and idempotent operation replay at the database
  level.
* Keep future reincarnation history, cultivation, item provenance, and social
  systems extensible without adding speculative columns to `accounts`.
* Treat `life_id` as the aggregate identity for a complete mortal incarnation.
  Future cultivation, vitality, sect, technique, combat, inventory, travel, and
  social records attach to the life through their owning modules. The first A
  migration creates only the subset backed by implemented gameplay, while the
  design documents the full mapping from the old bot vocabulary.
* Minecraft cultivation uses an active-world-entry plus offline-settlement loop:
  combat rewards first create stored/unrefined cultivation for the current
  character; the player must travel to an eligible cultivation area, choose a
  compatible technique, and start seclusion before that reserve can be converted
  into actual realm progress. A persisted seclusion session remains effective
  while the player is offline.
* Stored combat cultivation and realized cultivation progress are separate
  authoritative values. Combat cannot directly advance the realm bar, and
  seclusion cannot create progress without consuming/settling an allowed source
  reserve under the selected technique and area rules.
* The old bot's idle-travel/exploration mode is not part of the Minecraft design.
  Minecraft world travel is active gameplay; only seclusion retains offline
  progression semantics.
* Unrefined cultivation, realized cultivation, realm/stage, spirit root, pill
  poison, heart-demon state, and ordinary items are life-scoped and do not carry
  into a new generation.
* Cross-life inheritance is allowlisted at the account layer, not inherited by
  default. The confirmed permanent asset is technique-mark layer count. Future
  inherited items remain provenance-bearing account entitlements with explicit
  later-life acquisition/use conditions rather than automatic item duplication.
* A technique may grant at most one mark layer per life. The same technique may
  grant another layer in a later life after being mastered again. Persistence
  uses an account-level aggregate plus append-only mark events with a unique
  `(source_life_id, technique_id)` grant constraint. Any total layer cap belongs
  to the version-controlled technique definition, not the account row schema.
* Avoid floating-point persistence for authoritative probabilities and rates.
  Store exact integer/fixed-point units (for example basis points) and calculate
  effective values deterministically in the Cultivation service.
* Historical player lives are retained in their owning domain tables rather
  than copied into a generic archive. Future life recaps or annual player
  reports will use versioned read-model snapshots/analytics derived from life,
  cultivation, quest, combat, item, and activity facts; technical idempotency
  rows must not be counted as gameplay activity.
* Record schema decisions, rejected alternatives, and mapping notes from the
  old bot in this task's design artifacts.

## Decision (ADR-lite)

**Context**: The previous QQ bot schema is a useful domain reference but mixes
identity, current-life state, temporary runtime fields, and future systems in a
single player table. The Minecraft service needs restart-safe state now while
remaining extensible for reincarnation, cultivation, items, combat, and future
content authoring.

**Decision**:

* Use clean Minecraft-native identity keyed by stable Minecraft UUIDs; no
  permanent QQ compatibility fields.
* Persist the core vertical slice only: accounts, name history, lives,
  immutable per-life spirit roots, quest progress, a per-life quest revision
  row, and idempotent quest operations.
* Keep quest definitions and trigger definitions in version-controlled code or
  content files for now. Store `definition_version` on player progress so a
  later content database can be introduced independently.
* Keep fixed spirit-root elements as stable application codes with database
  constraints, not a mutable element catalog table.
* Treat a life as immutable spirit-root assignment plus a terminal
  `alive -> reincarnated` state transition. Ordinary Minecraft deaths do not
  close a life.
* Derive quest presentation states from persisted facts, authoritative module
  facts, and code-owned definitions. Do not persist duplicate objective counters
  or derived states.
* Keep quest operations as a compact exact-replay ledger. Do not treat them as
  gameplay analytics or player-visible history.

**Consequences**: The first migration is larger than replacing two dictionaries,
but it establishes durable identity, immutable life facts, database-enforced
concurrency, and a clean path for future modules. Online quest editing,
objective-specific projections, item/equipment persistence, and reincarnation
orchestration remain separate follow-up tasks.

## Technical Approach

### Core tables and ownership

* `accounts` (Player): internal UUID, unique Minecraft UUID, last-known name,
  revision, and lifecycle timestamps.
* `account_minecraft_names` (Player): per-account name observations with
  first/last seen timestamps; no global name uniqueness.
* `lives` (Player): one row per generation, generation number, alive/
  reincarnated status, revision, born/terminal death fields, and future death
  metadata slots.
* `life_spirit_roots` (Cultivation): one immutable row per life, fixed quality,
  constrained base-element codes, optional variant code, generator version, and
  detection timestamp.
* `life_quest_states` (Quest): one aggregate revision row per life.
* `quest_progress` (Quest): one row per `(life_id, quest_id)` with definition
  version, active/completed status, timestamps, and mutation revision.
* `quest_operations` (Quest): compact idempotency ledger containing request
  identity and the frozen success/error response produced by the same database
  transaction as the quest mutation.

All primary entities use PostgreSQL UUID keys. Foreign keys default to
restrict/no-action semantics; historical accounts, lives, roots, and progress
must not disappear through cascading deletes. All timestamps use
`TIMESTAMPTZ` and UTC-aware application values. Revisions use positive `BIGINT`
values and database-side atomic increments.

### Important constraints

* `accounts.minecraft_uuid` is unique.
* `account_minecraft_names` is unique per account and normalized name, not
  globally.
* `(account_id, generation_no)` is unique.
* A partial unique index permits at most one `alive` life per account.
  Current-life queries use this small partial index and never scan historical
  generations. Historical queries use `(account_id, generation_no)` ordering.
  Old lives remain in the same table unless measured production scale later
  justifies PostgreSQL partitioning or an analytics replica.
* `alive` lives have no terminal death timestamp; `reincarnated` lives must
  have one and cannot transition back.
* `life_spirit_roots.life_id` is a one-to-one primary/foreign key and has no
  normal update/delete path.
* `quest_progress` has primary key `(life_id, quest_id)` and only permits
  `active -> completed`.
* `quest_operations` has primary key `(life_id, operation_id)`; reusing an
  operation ID with a different request fingerprint is a conflict.

### Projection and transaction flow

Reads combine current-life facts, persisted quest rows, and code-owned
definitions. Objective evaluators query authoritative module contracts (for
example, spirit-root presence from Player/Cultivation) and return projection
values; they do not maintain duplicate counters.

Mutations lock the current life and `life_quest_states` row, apply the progress
transition, increment the quest revision only when state changes, and attach the
frozen response to the operation ledger atomically. A crash before commit rolls
back the operation and mutation together; a retry starts again. A retry after
commit replays the frozen result instead of re-evaluating current state.

The initial migration uses SQLAlchemy 2.x repositories and Alembic. It retains
the in-memory repositories for fast unit tests behind the same interfaces. The
deployment gate includes backup/PITR configuration and a real restore drill;
schema correctness alone is not an operational backup strategy.

## Implementation Plan (after design approval)

1. Add SQLAlchemy/Alembic bootstrap, database settings, and migration test
   harness.
2. Implement accounts, name observations, lives, and immutable spirit-root
   repositories with concurrency tests.
3. Implement quest aggregate revision, progress, and compact operation ledger
   repositories with transactional/idempotency tests.
4. Make PlayerService and QuestService use the PostgreSQL repositories in the
   application composition while preserving in-memory test injection.
5. Add restart, duplicate-request, life-isolation, and migration upgrade tests;
   document backup/restore and player-history query paths.

## Acceptance Criteria

* [x] First-migration scope is explicitly agreed.
* [x] Core table ownership and relationships are documented.
* [x] Realm/cultivation, spirit-root, reincarnation, quest, item, and social
      concepts are mapped to in-scope, deferred, or rejected status.
* [x] A migration-ready schema design exists with keys, constraints, indexes,
      timestamps, revision/concurrency strategy, and JSONB boundaries.
* [x] The design includes restart, retry, duplicate-request, and future evolution
      considerations.

## Definition of Done (team quality bar)

* Design reviewed and approved by the user before implementation.
* No implementation or migration code is written before design approval.
* Approved design is saved under `docs/superpowers/specs/` and linked here.
* Implementation plan is created only after the design review gate.

## Out of Scope (initial discussion)

* Directly importing the old QQ bot database into the Minecraft service.
* Implementing all market, dungeon, PVP, team, or item tables in the first
  persistence slice.
* Changing Paper/Citizens authoring behavior during schema design.
* Building the future life-recap/annual-report analytics pipeline in the first
  persistence slice.
* Choosing final cultivation duration, hourly rates, or time-to-realm targets
  during the PostgreSQL schema slice.

## Technical Notes

* Reference schema: `/home/adam/projects/mortals/init_db.py`.
* Current MC model files: `game-service/src/immortal_mmo/player/`,
  `game-service/src/immortal_mmo/quest/`.
* Project database conventions: `.trellis/spec/backend/database-guidelines.md`.
* Existing quest persistence requirements: `docs/superpowers/specs/2026-07-13-custom-quest-vertical-slice-design.md`.
* Approved design: `docs/superpowers/specs/2026-07-14-minecraft-postgresql-schema-design.md`.

## Research References

* [`research/mortals-numeric-design-reference.md`](research/mortals-numeric-design-reference.md)
  — maps the old bot's spirit-root rates, cultivation outcomes, breakthrough
  potential, pill poison, effect scopes, realm curve, and balance practices onto
  the MC long-term schema without copying float-heavy or monolithic storage.
