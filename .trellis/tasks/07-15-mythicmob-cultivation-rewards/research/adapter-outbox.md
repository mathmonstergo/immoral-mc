# Adapter SQLite WAL outbox research and decision

Research date: 2026-07-15

## Scope

The Paper Adapter must preserve an accepted MythicMobs kill fact while the Game
Service is unavailable or the Paper process restarts. SQLite is only a durable
delivery outbox; PostgreSQL remains the authority for combat facts, cultivation
ledger entries, current-life resolution, and balances.

## SQLite and JDBC choice

Use the Xerial SQLite JDBC driver in the Paper plugin runtime. The driver is
loaded by the plugin's own classloader and opens a file below the plugin data
folder (for example, `plugins/ImmortalMC/outbox.sqlite`). The database file is
not shared with the Game Service and is never treated as a progression store.

Connecting the Paper plugin directly to the central PostgreSQL database is
intentionally rejected. It would distribute database credentials to every
Minecraft server, let a plugin bypass Game Service authorization/current-life
logic, make remote database latency part of the tick path, and still lose the
event whenever the remote database is unavailable unless another queue were
added. The HTTP boundary keeps Game Service authoritative; SQLite is only the
small local bridge that lets the server survive a temporary boundary failure.

The dependency must be supplied through the same explicit plugin-library
mechanism used by the current Jackson dependency, or bundled only if the Paper
runtime/library loader cannot provide SQLite JDBC reliably. The final choice is
an implementation concern and must be verified against the target Paper
distribution; no Premium MythicMobs jar is involved.

## SQLite pragmas and schema

Each connection applies:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = FULL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

`WAL` permits the delivery reader to inspect pending rows while the single
writer commits a new fact. `synchronous=FULL` is deliberate: once the adapter
reports that a death fact was accepted, the transaction has synchronized its
WAL commit. The database is periodically checkpointed from the outbox worker;
checkpoint failure is logged and retried, not treated as permission to delete
unacknowledged rows.

The first schema is:

```sql
CREATE TABLE kill_outbox (
    event_id          TEXT PRIMARY KEY,
    server_id         TEXT NOT NULL,
    entity_uuid       TEXT NOT NULL,
    mob_internal_name TEXT NOT NULL,
    mob_level         REAL NOT NULL,
    killer_uuid       TEXT,
    world             TEXT NOT NULL,
    occurred_at_ms    INTEGER NOT NULL,
    payload_json      TEXT NOT NULL,
    delivery_status   TEXT NOT NULL DEFAULT 'pending',
    attempt_count     INTEGER NOT NULL DEFAULT 0,
    next_attempt_at_ms INTEGER NOT NULL,
    lease_until_ms    INTEGER,
    last_error        TEXT,
    created_at_ms     INTEGER NOT NULL,
    updated_at_ms     INTEGER NOT NULL,
    CHECK (delivery_status IN ('pending', 'in_flight', 'dead_letter')),
    CHECK (attempt_count >= 0)
);

CREATE INDEX ix_kill_outbox_due
    ON kill_outbox (delivery_status, next_attempt_at_ms);
```

`event_id` is deterministic for the configured `server_id` and dead entity
UUID. `payload_json` is the exact immutable request snapshot sent to the Game
Service; reward amounts are never stored in it. `lease_until_ms` makes a row
recoverable if the process dies after claiming it and before receiving an HTTP
result.

The outbox is not a permanent analytics table. A successfully acknowledged row
is removed, so its disk footprint is bounded by the outage/retry window. The
Game Service receives a compact event (IDs, mob code/level, killer, world and
time); it does not receive serialized Bukkit entities or inventories.

## Thread and durability model

1. The MythicMobs event listener runs on the Paper thread and copies only
   primitive/immutable facts from Bukkit/Mythic objects.
2. It submits the immutable snapshot to one bounded SQLite writer executor and
   waits for the short local transaction to commit. This wait is bounded by the
   SQLite busy timeout; it does not perform DNS, HTTP, JSON response handling,
   or Game Service work on the Paper thread.
3. The writer executes `INSERT ... ON CONFLICT(event_id) DO NOTHING` in a
   transaction. A duplicate event is an acknowledged no-op.
4. A separate delivery worker claims due rows with a short lease, performs the
   HTTP request, and then uses the writer executor for the acknowledgement or
   retry update. Only one SQLite writer exists; readers may query concurrently
   under WAL.
5. On startup, expired `in_flight` leases return to `pending`. The worker
   resumes delivery using the same `event_id`, so Game Service idempotency makes
   ambiguous post-HTTP crashes safe.

The durability guarantee is explicit: after the listener's append call returns
success, the immutable kill fact survives a normal process crash and power loss
to the extent provided by SQLite `synchronous=FULL` and the host filesystem.
If the local transaction cannot commit, the event is reported as capture
failure and no local reward fallback is attempted. This is stronger and more
honest than claiming that an asynchronous in-memory queue cannot lose events.

If profiling shows a very high kill rate, the same single writer can commit a
small micro-batch (for example, up to 32 events or a few milliseconds) in one
`synchronous=FULL` transaction. The API still returns capture success only
after the caller's row is included in a committed batch; this changes the
number of fsyncs, not the durability contract.

## Retry and terminal outcomes

Retry transport failures, timeouts, HTTP 408/429, and 5xx responses with capped
exponential backoff and jitter. Increment `attempt_count`, set
`next_attempt_at_ms`, clear the lease, and retain `last_error`.

Delete/acknowledge rows after Game Service confirms `accepted`, `duplicate`, or
another explicit terminal domain result such as `not_rewardable` or
`current_life_unavailable`; those outcomes are authoritative and must not be
retried forever. Malformed local rows, invalid JSON, or unrecoverable 4xx
responses transition to `dead_letter` with a visible error and remain
inspectable for operators.

The worker never invents a cultivation amount and never mutates PostgreSQL
directly. It sends the immutable kill fact to the Game Service endpoint, which
performs combat-fact insertion, current-life validation, catalog calculation,
reward-ledger deduplication, and unrefined-cultivation increment in one
transaction.

## Operational safeguards

* Bound the writer queue and expose capture-failure/dead-letter metrics.
* Log event ID, mob ID, attempt count, and outcome; do not log arbitrary player
  payloads at info level.
* Keep the SQLite file under the plugin data directory and include it in the
  server backup policy.
* Never copy the SQLite file between servers with the same `server_id` unless
  the operator intentionally accepts replay deduplication semantics.
