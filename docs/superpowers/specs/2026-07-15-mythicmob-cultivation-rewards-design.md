# MythicMobs Kill Cultivation Rewards Design

**Date:** 2026-07-15  
**Status:** Approved  
**Task:** `.trellis/tasks/07-15-mythicmob-cultivation-rewards`

## 1. Purpose

Connect official free-distribution MythicMobs 5.12.1 death events to the
authoritative Game Service. A qualifying player kill credits the current
life's unrefined cultivation exactly once, records a compact monster kill fact,
and increments a per-life/per-monster counter.

Combat rewards remain reserve only. They do not advance realm progress until a
future seclusion flow consumes and refines that reserve.

## 2. Ownership Boundaries

```text
MythicMobDeathEvent
  -> Paper Adapter snapshots immutable server facts
  -> local SQLite WAL outbox commits the delivery item
  -> asynchronous HTTP delivery
  -> Game Service authenticates/validates the request boundary
  -> PostgreSQL stores the kill fact and count
  -> Game Service reward catalog calculates cultivation
  -> cultivation ledger credits unrefined cultivation
```

MythicMobs owns mob definitions, spawning, AI, skills, levels, presentation,
and ordinary Mythic content. The Adapter owns typed event capture and reliable
delivery. The Game Service owns account/current-life resolution, rewardability,
reward calculation, deduplication, counters, ledgers, and balances. PostgreSQL
is the only gameplay source of truth.

The Adapter never accepts a reward amount from MythicMobs YAML, never calculates
an authoritative amount, and never writes PostgreSQL directly. SQLite is not a
second progression database.

## 3. Supported MythicMobs Integration

The first release compiles against the official artifact:

```kotlin
compileOnly("io.lumine:Mythic-Dist:5.12.1")
```

from:

```text
https://mvn.lumine.io/repository/maven-public/
```

The dependency is not shaded into ImmortalMC. `plugin.yml` declares
`MythicMobs` as a soft dependency. A dedicated loader registers a typed
`MythicMobDeathEvent` listener only when MythicMobs is enabled.

If MythicMobs is absent, unrelated ImmortalMC features continue and the missing
integration is logged. If it is present but binary-incompatible, the MythicMobs
integration fails visibly and does not fall back to entity names, lore,
`EntityDeathEvent` heuristics, or a mandatory `~onDeath` mechanic.

Premium artifacts, credentials, and Premium-only APIs are excluded from source,
CI, dependencies, and release artifacts. A future legally licensed Premium
extension must reuse the same Adapter/outbox/Game Service authority boundary.

## 4. Monster Authoring Workflow

Content authors create mobs with the normal MythicMobs format. The top-level
Mythic mob key is the stable integration ID:

```yaml
# plugins/MythicMobs/mobs/ImmortalMobs.yml
AzureWolf:
  Type: WOLF
  Display: '&bAzure Wolf'
  Health: 80
  Damage: 8

AzureDragon:
  Type: ENDER_DRAGON
  Display: '&5Azure Dragon'
  Health: 5000
  Damage: 40
```

The Game Service owns a separate version-controlled catalog keyed by the exact
`MythicMob#getInternalName()` value:

```yaml
schema_version: 1
mobs:
  AzureWolf:
    reward_profile: ordinary_wolf
    telemetry: compact
  AzureDragon:
    reward_profile: azure_dragon
    telemetry: detailed
```

No arbitrary custom MythicMobs field is required. Unknown internal names return
the stable `not_rewardable` outcome and do not receive a default reward. A
content change that renames a Mythic internal name must update the Game Service
catalog in the same release.

`reward_profile` selects Game Service-owned integer rules and an optional shared
versioned level curve. `telemetry` is either `compact` or `detailed`. Ordinary
mobs use compact facts; bosses or named special mobs may preserve an additional
small JSONB detail snapshot. MythicMobs YAML remains presentation/combat content,
not progression authority.

## 5. Adapter Event Contract

The listener accepts only `MythicMobDeathEvent` instances whose killer is a
Paper `Player`. Environmental deaths, despawns, and non-player kills do not
enter the reward outbox in this slice.

On the Paper thread, the listener copies these values and then releases all
Bukkit/Mythic object references:

* configured `server_id`;
* deterministic `event_id` derived from `server_id` and dead entity UUID;
* dead entity UUID;
* exact Mythic internal name;
* finite Mythic mob level;
* killer Minecraft UUID;
* world key and coordinates;
* UTC occurrence timestamp;
* request contract version.

Coordinates are sent as candidate detail but are persisted permanently only
when the Game Service catalog selects `detailed`. No inventory, drops, Bukkit
object serialization, damage history, or trusted reward amount is included.

The version-one request is conceptually:

```json
{
  "contract_version": 1,
  "event_id": "uuid",
  "server_id": "main-1",
  "entity_uuid": "uuid",
  "mob_internal_name": "AzureWolf",
  "mob_level": "12.000",
  "killer_uuid": "uuid",
  "world": "minecraft:overworld",
  "x": 120.5,
  "y": 64.0,
  "z": -33.25,
  "occurred_at": "2026-07-15T12:00:00Z"
}
```

Mob level crosses the boundary as a bounded decimal string and is parsed into a
fixed-precision decimal. NaN, infinities, negative values, excessive precision,
and configured upper-bound violations are invalid requests, not coercions.

## 6. SQLite Durable Outbox

### 6.1 Why it exists

The outbox is a local pending-delivery mailbox. It preserves a kill after the
Minecraft event occurs but before the remote Game Service acknowledges it. A
memory-only queue would lose that kill on a Paper crash; a direct PostgreSQL
connection would distribute credentials, bypass Game Service rules, expose the
tick path to remote latency, and still need a queue during database outages.

SQLite lives below the ImmortalMC plugin data folder and contains no gameplay
balance. A row is removed after a terminal Game Service acknowledgement, so
normal disk use is bounded by the current outage/retry window.

### 6.2 Connection settings

Every connection applies:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

The plugin uses Xerial SQLite JDBC through the verified Paper plugin-library
loading path. WAL permits concurrent delivery reads while the single writer
commits. `synchronous=FULL` means capture success is returned only after the
local WAL transaction is synchronized to the extent provided by SQLite and the
host filesystem.

### 6.3 Schema

```sql
CREATE TABLE kill_outbox (
    event_id            TEXT PRIMARY KEY,
    server_id           TEXT NOT NULL,
    entity_uuid         TEXT NOT NULL,
    mob_internal_name   TEXT NOT NULL,
    mob_level           TEXT NOT NULL,
    killer_uuid         TEXT NOT NULL,
    world               TEXT NOT NULL,
    occurred_at_ms      INTEGER NOT NULL,
    payload_json        TEXT NOT NULL,
    delivery_status     TEXT NOT NULL DEFAULT 'pending',
    attempt_count       INTEGER NOT NULL DEFAULT 0,
    next_attempt_at_ms  INTEGER NOT NULL,
    lease_until_ms      INTEGER,
    last_error          TEXT,
    created_at_ms       INTEGER NOT NULL,
    updated_at_ms       INTEGER NOT NULL,
    CHECK (delivery_status IN ('pending', 'in_flight', 'dead_letter')),
    CHECK (attempt_count >= 0)
);

CREATE INDEX ix_kill_outbox_due
    ON kill_outbox (delivery_status, next_attempt_at_ms);
```

`payload_json` is the exact compact HTTP request snapshot. Reward amounts never
appear in the outbox.

### 6.4 Threads and durability

One bounded writer executor serializes all SQLite writes. The listener submits
the immutable event and waits for its short local transaction to commit. This
wait may include local disk latency, but never DNS, HTTP, Game Service response
processing, or retry delay.

The writer uses `INSERT ... ON CONFLICT(event_id) DO NOTHING`. A delivery worker
claims due rows with an expiring lease, performs HTTP off the Paper thread, and
returns acknowledgement/retry mutations to the writer executor. Startup
reclaims expired `in_flight` rows.

If profiling reveals high kill throughput, the writer may micro-batch up to 32
queued inserts or a few milliseconds into one FULL transaction. Each caller is
completed only after its row's batch commits; batching reduces fsync count
without weakening the capture contract.

After append success, the kill survives ordinary process crashes and power loss
to the guarantees of SQLite FULL and the filesystem. A failed local commit is a
visible capture failure; no local reward fallback is granted.

### 6.5 Retry outcomes

Transport errors, timeouts, HTTP 408/429, and 5xx responses use capped
exponential backoff with jitter. The row retains attempt count, next-attempt
time, lease state, and the latest concise error.

The worker deletes the row after `accepted`, `duplicate`, `not_rewardable`,
`account_not_found`, or `current_life_unavailable`. These are explicit terminal
Game Service decisions. Invalid local JSON and unrecoverable 4xx responses move
to `dead_letter`, remain operator-visible, and do not retry forever.

An HTTP timeout after PostgreSQL commit is safe: the same deterministic event
ID is retried, and Game Service returns the frozen prior result without a second
credit.

## 7. PostgreSQL Model

### 7.1 `life_cultivation_states`

One mutable cultivation aggregate per life:

```sql
CREATE TABLE life_cultivation_states (
    life_id                 UUID PRIMARY KEY
                            REFERENCES lives(life_id) ON DELETE RESTRICT,
    unrefined_cultivation   BIGINT NOT NULL DEFAULT 0
                            CHECK (unrefined_cultivation >= 0),
    realized_cultivation    BIGINT NOT NULL DEFAULT 0
                            CHECK (realized_cultivation >= 0),
    revision                BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

This slice changes only `unrefined_cultivation` and `revision`. Realm/stage,
breakthrough, pill poison, heart demon, effects, and seclusion are later
additive migrations or modules.

### 7.2 `combat_kill_events`

One compact immutable player-kill fact and its immutable processing result:

```sql
CREATE TABLE combat_kill_events (
    kill_event_id          UUID PRIMARY KEY,
    source_type            VARCHAR(32) NOT NULL,
    source_event_id        UUID NOT NULL,
    server_id              VARCHAR(64) NOT NULL,
    entity_uuid            UUID NOT NULL,
    mob_internal_name      VARCHAR(128) NOT NULL,
    mob_level              NUMERIC(12,3) NOT NULL,
    killer_minecraft_uuid  UUID NOT NULL,
    account_id             UUID NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    life_id                UUID NULL REFERENCES lives(life_id) ON DELETE RESTRICT,
    world_key              VARCHAR(128) NOT NULL,
    occurred_at            TIMESTAMPTZ NOT NULL,
    outcome                VARCHAR(32) NOT NULL,
    telemetry              VARCHAR(16) NOT NULL,
    detail_payload         JSONB NULL,
    reward_amount          BIGINT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_combat_kill_source UNIQUE (source_type, source_event_id),
    CONSTRAINT ck_combat_kill_source_type
        CHECK (source_type = 'mythicmob_death'),
    CONSTRAINT ck_combat_kill_level CHECK (mob_level >= 0),
    CONSTRAINT ck_combat_kill_outcome CHECK (
        outcome IN ('rewarded', 'not_rewardable', 'account_not_found',
                    'current_life_unavailable')
    ),
    CONSTRAINT ck_combat_kill_telemetry
        CHECK (telemetry IN ('compact', 'detailed')),
    CONSTRAINT ck_combat_kill_detail CHECK (
        (telemetry = 'compact' AND detail_payload IS NULL)
        OR telemetry = 'detailed'
    ),
    CONSTRAINT ck_combat_kill_reward_shape CHECK (
        (outcome = 'rewarded'
            AND account_id IS NOT NULL
            AND life_id IS NOT NULL
            AND reward_amount IS NOT NULL
            AND reward_amount > 0)
        OR
        (outcome <> 'rewarded' AND reward_amount IS NULL)
    )
);

CREATE INDEX ix_combat_kills_life_time
    ON combat_kill_events (life_id, occurred_at DESC)
    WHERE life_id IS NOT NULL;

CREATE INDEX ix_combat_kills_mob_time
    ON combat_kill_events (mob_internal_name, occurred_at DESC);
```

Ordinary rows contain no permanent JSON payload. Detailed rows may preserve
location and future explicitly allowlisted boss context. The first slice does
not store complete damage contribution history.

The compact event row is retained initially because it is the strongest
idempotency and audit record. Product-facing counts never scan it. If measured
volume later justifies retention or partitioning, counters and annual read
models remain stable while the event storage policy changes independently.

### 7.3 `life_mob_kill_counters`

Fast product-facing count projection:

```sql
CREATE TABLE life_mob_kill_counters (
    life_id             UUID NOT NULL REFERENCES lives(life_id) ON DELETE RESTRICT,
    mob_internal_name   VARCHAR(128) NOT NULL,
    kill_count          BIGINT NOT NULL CHECK (kill_count > 0),
    first_killed_at     TIMESTAMPTZ NOT NULL,
    last_killed_at      TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (life_id, mob_internal_name),
    CONSTRAINT ck_life_mob_kill_time
        CHECK (last_killed_at >= first_killed_at)
);
```

Every recognized/rewarded current-life kill increments this row atomically.
Quest projections, player statistics, and annual reports read counters or
dedicated read models instead of counting raw event rows.

### 7.4 `cultivation_resource_entries`

Append-only cultivation resource ledger:

```sql
CREATE TABLE cultivation_resource_entries (
    entry_id          UUID PRIMARY KEY,
    life_id           UUID NOT NULL REFERENCES lives(life_id) ON DELETE RESTRICT,
    resource_code     VARCHAR(32) NOT NULL,
    entry_type        VARCHAR(32) NOT NULL,
    delta_amount      BIGINT NOT NULL,
    balance_after     BIGINT NOT NULL CHECK (balance_after >= 0),
    kill_event_id     UUID NULL
                      REFERENCES combat_kill_events(kill_event_id) ON DELETE RESTRICT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_cultivation_resource_code
        CHECK (resource_code IN ('unrefined_cultivation', 'realized_cultivation')),
    CONSTRAINT ck_cultivation_entry_type
        CHECK (entry_type IN ('combat_reward', 'seclusion_consumption',
                              'seclusion_realization', 'administrative_adjustment')),
    CONSTRAINT ck_cultivation_entry_delta CHECK (delta_amount <> 0),
    CONSTRAINT ck_cultivation_combat_source CHECK (
        (entry_type = 'combat_reward'
            AND resource_code = 'unrefined_cultivation'
            AND delta_amount > 0
            AND kill_event_id IS NOT NULL)
        OR entry_type <> 'combat_reward'
    )
);

CREATE UNIQUE INDEX ux_cultivation_kill_recipient
    ON cultivation_resource_entries (kill_event_id, life_id, resource_code)
    WHERE entry_type = 'combat_reward';
```

The uniqueness shape permits multiple future recipient lives for one kill while
preventing duplicate credit to the same life. This slice writes only positive
`combat_reward` entries for unrefined cultivation.

## 8. Game Service Transaction

For a new request:

1. Validate the wire contract, exact internal name syntax, decimal level, UUIDs,
   and occurrence time before opening a database transaction.
2. Resolve the reward/telemetry catalog entry. Unknown IDs select the terminal
   `not_rewardable` outcome; no implicit reward is used.
3. Begin one short PostgreSQL transaction.
4. Look up `(source_type, source_event_id)`. If it exists, validate immutable
   request identity and return the stored result. A mismatched replay is an
   idempotency conflict.
5. Resolve and lock the account by killer Minecraft UUID. If absent, insert the
   compact event with `account_not_found` and return the terminal result.
6. Resolve and lock the account's current `alive` life. If absent, insert the
   event with `current_life_unavailable`; never bind the kill to a historical
   or later life.
7. For a recognized catalog entry, calculate the positive integer reward with
   the versioned Game Service profile and checked arithmetic.
8. Insert the immutable combat kill event, including the selected compact or
   detailed telemetry policy.
9. Upsert/increment `life_mob_kill_counters`.
10. Lock or lazily create `life_cultivation_states`.
11. Append one `cultivation_resource_entries` row, update unrefined cultivation
    and cultivation revision, and record the resulting balance.
12. Commit and return the immutable result.

The lock order is `accounts`, current `lives`, combat source reservation,
counter, cultivation state, then cultivation ledger insertion. No network,
Paper API, or MythicMobs API call occurs inside the transaction.

Concurrent deliveries use the source unique key as the final race guard. A
unique conflict is handled by rolling back/retrying the short transaction and
loading the committed source result; code never continues in an aborted
SQLAlchemy transaction.

## 9. HTTP Outcomes

All valid terminal domain outcomes use a stable response body and are safe for
the Adapter to acknowledge:

* `accepted`: newly processed and rewarded;
* `duplicate`: exact replay of an already processed event, including its
  original outcome/amount/balance snapshot;
* `not_rewardable`: unknown or intentionally disabled catalog ID;
* `account_not_found`: killer UUID has no Game Service account;
* `current_life_unavailable`: no current alive life exists.

Contract validation and idempotency identity conflicts are non-retryable 4xx
responses and become Adapter dead letters. Unexpected server/database failures
are 5xx and remain retryable. The Adapter never interprets an ambiguous timeout
as success.

## 10. Reward Catalog Rules

Catalog loading fails application startup/readiness on:

* duplicate or invalid internal names;
* unknown reward profiles or level curves;
* non-positive base rewards for enabled entries;
* invalid decimal level bounds;
* unsupported telemetry modes;
* arithmetic overflow risk;
* schema-version mismatch.

Final gameplay balance values are intentionally not selected by this design.
The implementation supplies the catalog loader, checked deterministic
calculation contracts, and test fixtures. Production reward values are added
only through a reviewed content change; no hidden fallback amount exists.

## 11. Performance and Operations

The hot Paper path performs a typed event snapshot and a bounded local SQLite
commit only. Remote work is asynchronous. Ambient/non-player deaths are
filtered before SQLite.

The SQLite outbox deletes acknowledged rows and therefore reflects outage
backlog rather than lifetime kill volume. Operators monitor pending count,
oldest pending age, retry rate, dead-letter count, capture failures, and local
database/checkpoint failures.

PostgreSQL writes one compact event, one counter upsert, one ledger entry, and
one cultivation-state update per rewarded kill in a single transaction. Count
queries use the counter primary key. Ordinary events carry no permanent JSON;
Boss detail is explicitly catalog-controlled.

Initial operation retains compact events. Before measured write rate or table
size becomes material, no premature partition/archive machinery is added. When
measurements justify it, raw events may move to time partitioning/retention and
annual reports to materialized/read-replica projections without changing the
counter or cultivation contracts.

## 12. Testing

### Game Service

Unit tests cover catalog schema validation, exact ID lookup, decimal level
boundaries, deterministic reward rounding, unknown IDs, and overflow rejection.

PostgreSQL integration tests cover:

* one kill credits the current life once;
* exact replay returns the original result without a second counter or reward;
* mismatched replay conflicts;
* missing account and missing current life terminal outcomes;
* reincarnation never rebinds an old event to a new life;
* concurrent duplicate delivery;
* atomic rollback across event, counter, ledger, and balance;
* compact versus detailed payload persistence;
* database restart persistence and dump/restore compatibility.

### Paper Adapter

Java tests cover MythicMobs present, absent, and incompatible; typed event
mapping; non-player kill filtering; stable event IDs; decimal level validation;
and release of Bukkit object references before asynchronous work.

SQLite tests cover WAL/FULL configuration, duplicate enqueue, bounded writer
queue, optional micro-batching, successful acknowledgement, lease recovery,
retry classification/backoff, dead-letter handling, checkpoint behavior, and
Paper restart replay. Tests assert that no network call executes on the Paper
thread.

### Smoke test

A real Paper server with official free MythicMobs 5.12.1 proves:

1. a configured ordinary mob increments its kill counter and unrefined reserve;
2. a configured boss produces detailed telemetry;
3. an unknown mob produces no reward;
4. a kill during Game Service downtime stays in SQLite;
5. Paper and Game Service restarts preserve and redeliver the event;
6. recovery credits exactly once and survives a subsequent PostgreSQL restart.

## 13. Explicitly Deferred

* final reward values and time-to-realm balance;
* seclusion and realized-cultivation progression;
* party/contribution sharing and damage histories;
* anti-boosting, caps, rested bonuses, loot, and vanilla-mob rewards;
* world-wide non-player death analytics;
* Premium-only mechanics;
* online content editing and live catalog reload;
* event partitioning/retention before measured scale requires it.
