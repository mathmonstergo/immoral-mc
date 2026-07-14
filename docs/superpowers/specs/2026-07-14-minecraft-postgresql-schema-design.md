# Minecraft PostgreSQL Schema Design

**Date:** 2026-07-14  
**Status:** Approved; implementation authorized  
**Task:** `.trellis/tasks/07-14-postgresql-schema-design`

## 1. Purpose

Replace the Game Service's restart-volatile player and quest repositories with
a PostgreSQL design that can support a long-running Minecraft MMORPG.

The first migration persists only gameplay that already exists:

* permanent Minecraft accounts and observed names;
* per-generation lives;
* immutable per-life spirit roots;
* quest aggregate revision, progress, and request idempotency.

The schema is intentionally narrower than the old QQ bot database, but the
design preserves the full life aggregate required for cultivation, offline
seclusion, techniques, sects, items, combat, reincarnation, inheritance, and
future player recaps.

## 2. Domain Boundaries

```text
Account (permanent)
├── Minecraft identity and name history
├── technique-mark layers (future)
└── conditional inherited-item entitlements (future)

Life (one mortal generation)
├── immutable spirit root
├── realm and cultivation state (future)
├── unrefined and realized cultivation (future)
├── seclusion sessions and effects (future)
├── vitality, pill poison, and heart-demon state (future)
├── techniques, sect, inventory, equipment, combat, and travel (future)
└── quest state
```

Only explicitly allowlisted assets cross generations. Realm, cultivation,
spirit root, ordinary items, pill poison, heart-demon state, quests, and social
memberships are life-scoped and do not carry into a new life.

The current cross-life asset is technique-mark layer count. Future inherited
items are account entitlements with provenance and unlock/use conditions; they
are not automatically copied into a new inventory.

## 3. Storage Principles

* PostgreSQL is authoritative for durable gameplay state.
* Redis is not required for this slice and must not become a progression source
  of truth.
* Entity IDs use PostgreSQL `UUID` columns.
* Timestamps use `TIMESTAMPTZ`; the application uses timezone-aware UTC values.
* Revisions use `BIGINT` and database-side atomic increments.
* Statuses use constrained strings rather than PostgreSQL enums so future
  migrations remain straightforward.
* Foreign keys use `RESTRICT`/`NO ACTION` by default. Historical lives, roots,
  and progress must not disappear through cascading deletes.
* Core query fields use typed columns. JSONB is reserved for versioned opaque
  snapshots or flexible future payloads.
* Display text is not identity. Stable codes are persisted; localized labels
  are derived from version-controlled definitions.
* Internal Player domain models contain only stable codes and authoritative
  facts. HTTP/Paper presentation models are separate and derive the current
  Chinese labels/elements at the API boundary; database mappers never reverse-
  parse localized strings.
* Production must fail startup/readiness when PostgreSQL is unavailable. It must
  never silently fall back to an in-memory repository.
* This is a pre-production 0-to-1 clean break. Existing synchronous services,
  lease-based in-memory quest operations, API internals, tests, and disposable
  development data do not receive compatibility adapters.
* The implementation is async end to end: FastAPI routes, application services,
  repositories, Unit of Work, SQLAlchemy `AsyncSession`, and asyncpg.
* Tests may inject explicit fakes, but services have no default in-memory
  repository and runtime composition has no fallback path.

## 4. Core Schema

### 4.1 `accounts`

Permanent login-linked identity.

```sql
CREATE TABLE accounts (
    account_id       UUID PRIMARY KEY,
    minecraft_uuid   UUID NOT NULL UNIQUE,
    last_known_name  VARCHAR(16) NOT NULL
                     CHECK (last_known_name ~ '^[A-Za-z0-9_]{3,16}$'),
    revision         BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Meaning |
|---|---|
| `account_id` | Internal permanent account identity. |
| `minecraft_uuid` | Stable Minecraft identity; player names never replace it. |
| `last_known_name` | Most recently observed Minecraft display name. |
| `revision` | Account-profile version for concurrency and cache invalidation. |
| `created_at` | First account creation time. |
| `updated_at` | Last account-profile update time. |
| `last_seen_at` | Most recent successful login/observation time. |

Login uses one atomic upsert keyed by `minecraft_uuid`. Existing accounts update
`last_known_name`, `last_seen_at`, and `updated_at`; a name change also advances
the account revision.

No QQ/legacy identity column is retained. A future one-off import may use an
external SQL/ETL mapping without changing the runtime schema.

### 4.2 `account_minecraft_names`

Append-preserving name observations for support, moderation, and audit queries.

```sql
CREATE TABLE account_minecraft_names (
    name_observation_id  UUID PRIMARY KEY,
    account_id           UUID NOT NULL
                         REFERENCES accounts(account_id) ON DELETE RESTRICT,
    player_name          VARCHAR(16) NOT NULL,
    normalized_name      VARCHAR(16) NOT NULL,
    first_seen_at        TIMESTAMPTZ NOT NULL,
    last_seen_at         TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_account_minecraft_name
        UNIQUE (account_id, normalized_name),
    CONSTRAINT ck_account_name_seen_order
        CHECK (last_seen_at >= first_seen_at),
    CONSTRAINT ck_account_name_format
        CHECK (player_name ~ '^[A-Za-z0-9_]{3,16}$'),
    CONSTRAINT ck_account_name_normalized
        CHECK (normalized_name = lower(player_name))
);

CREATE INDEX ix_account_names_normalized
    ON account_minecraft_names (normalized_name, last_seen_at DESC);
```

| Column | Meaning |
|---|---|
| `name_observation_id` | Internal observation row identity. |
| `account_id` | Account that used the name. |
| `player_name` | Last observed casing of the display name. |
| `normalized_name` | ASCII-lowercased Java username for per-account deduplication. |
| `first_seen_at` | First observation time for this account/name pair. |
| `last_seen_at` | Most recent observation time for this account/name pair. |

Names are not globally unique because Minecraft names may later be reused by a
different UUID. Login upserts this row and extends `last_seen_at`.

Normalization is exactly ASCII lowercase after validating the Java username
pattern `[A-Za-z0-9_]{3,16}`. Application and database tests use the same rule.

### 4.3 `lives`

One row per mortal generation. Historical generations remain in this table;
they are terminal domain records, not manually moved archive rows.

```sql
CREATE TABLE lives (
    life_id            UUID PRIMARY KEY,
    account_id         UUID NOT NULL
                       REFERENCES accounts(account_id) ON DELETE RESTRICT,
    generation_no      INTEGER NOT NULL CHECK (generation_no > 0),
    status             VARCHAR(20) NOT NULL,
    revision           BIGINT NOT NULL DEFAULT 1 CHECK (revision > 0),
    born_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    died_at            TIMESTAMPTZ NULL,
    death_cause_code   VARCHAR(64) NULL,
    death_zone_id      VARCHAR(128) NULL,
    CONSTRAINT uq_life_generation UNIQUE (account_id, generation_no),
    CONSTRAINT uq_life_account UNIQUE (life_id, account_id),
    CONSTRAINT ck_life_status CHECK (status IN ('alive', 'reincarnated')),
    CONSTRAINT ck_life_terminal_fields CHECK (
        (status = 'alive'
            AND died_at IS NULL
            AND death_cause_code IS NULL
            AND death_zone_id IS NULL)
        OR
        (status = 'reincarnated'
            AND died_at IS NOT NULL
            AND death_cause_code IS NOT NULL)
    ),
    CONSTRAINT ck_life_time_order CHECK (died_at IS NULL OR died_at >= born_at)
);

CREATE UNIQUE INDEX ux_lives_one_alive_per_account
    ON lives (account_id)
    WHERE status = 'alive';

CREATE FUNCTION prevent_life_delete_or_terminal_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'life rows are not deleted';
    END IF;
    IF OLD.status = 'reincarnated' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'reincarnated life is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_lives_prevent_delete_terminal_mutation
BEFORE UPDATE OR DELETE ON lives
FOR EACH ROW EXECUTE FUNCTION prevent_life_delete_or_terminal_mutation();
```

| Column | Meaning |
|---|---|
| `life_id` | Stable identity for one incarnation and all life-owned records. |
| `account_id` | Permanent account that owns the life. |
| `generation_no` | Generation number, beginning at 1. |
| `status` | `alive` or terminal `reincarnated`. |
| `revision` | Version of current-life/player facts. |
| `born_at` | Life creation time. |
| `updated_at` | Last life-fact update time. |
| `died_at` | Time the Game Service conclusively ended the life. |
| `death_cause_code` | Stable terminal cause such as `red_zone_no_protection`. |
| `death_zone_id` | Semantic zone where the terminal decision occurred; nullable for non-zone administrative or future causes. |

Ordinary Minecraft deaths in green/yellow zones or protected red-zone deaths do
not change `lives.status` and do not populate terminal fields. Only a Game
Service reincarnation decision performs `alive -> reincarnated`.

Current-life lookup is always explicit:

```sql
SELECT * FROM lives
WHERE account_id = :account_id AND status = 'alive';
```

The partial unique index contains only living generations, so historical growth
does not make login scan old lives. History uses the existing
`(account_id, generation_no)` unique index.

### 4.4 `life_spirit_roots`

Player-owned immutable life-birth fact for the first slice. One life receives
exactly one spirit root. A future cultivation slice may extract ownership behind
an explicit service boundary without changing the table identity.

```sql
CREATE FUNCTION is_valid_spirit_root(
    root_quality VARCHAR,
    root_elements TEXT[],
    root_variant VARCHAR
)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT
        array_ndims(root_elements) = 1
        AND array_position(root_elements, NULL) IS NULL
        AND root_elements = ARRAY(
            SELECT element_code
            FROM unnest(ARRAY['metal','wood','water','fire','earth']::TEXT[])
                 AS elements(element_code)
            WHERE element_code = ANY(root_elements)
        )
        AND (
            (root_quality = 'penta'
                AND cardinality(root_elements) = 5
                AND root_variant IS NULL)
            OR
            (root_quality = 'quad'
                AND cardinality(root_elements) = 4
                AND root_variant IS NULL)
            OR
            (root_quality = 'triple'
                AND cardinality(root_elements) = 3
                AND root_variant IS NULL)
            OR
            (root_quality = 'dual'
                AND cardinality(root_elements) = 2
                AND root_variant IS NULL)
            OR
            (root_quality = 'celestial'
                AND cardinality(root_elements) = 1
                AND root_variant IS NULL)
            OR
            (root_quality = 'variant'
                AND cardinality(root_elements) = 1
                AND (
                    (root_elements = ARRAY['fire']::TEXT[]
                        AND root_variant IN ('wind', 'thunder'))
                    OR (root_elements = ARRAY['wood']::TEXT[]
                        AND root_variant IN ('wind', 'ice'))
                    OR (root_elements = ARRAY['metal']::TEXT[]
                        AND root_variant IN ('thunder', 'dark'))
                    OR (root_elements = ARRAY['water']::TEXT[]
                        AND root_variant IN ('thunder', 'ice'))
                    OR (root_elements = ARRAY['earth']::TEXT[]
                        AND root_variant = 'dark')
                ))
        );
$$;

CREATE TABLE life_spirit_roots (
    life_id                         UUID PRIMARY KEY
                                    REFERENCES lives(life_id) ON DELETE RESTRICT,
    quality_code                    VARCHAR(20) NOT NULL,
    base_element_codes              TEXT[] NOT NULL,
    variant_element_code            VARCHAR(20) NULL,
    generator_version               INTEGER NOT NULL CHECK (generator_version > 0),
    detected_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_spirit_root_quality CHECK (
        quality_code IN ('quad', 'penta', 'triple', 'dual', 'variant', 'celestial')
    ),
    CONSTRAINT ck_spirit_root_shape CHECK (
        is_valid_spirit_root(
            quality_code,
            base_element_codes,
            variant_element_code
        ) IS TRUE
    )
);

CREATE FUNCTION prevent_spirit_root_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'spirit root is immutable';
END;
$$;

CREATE TRIGGER trg_spirit_roots_prevent_update_delete
BEFORE UPDATE OR DELETE ON life_spirit_roots
FOR EACH ROW EXECUTE FUNCTION prevent_spirit_root_mutation();
```

| Column | Meaning |
|---|---|
| `life_id` | One-to-one life identity. |
| `quality_code` | Stable root quality code. |
| `base_element_codes` | Fixed base elements using stable English codes. |
| `variant_element_code` | Optional mutation component. |
| `generator_version` | Versioned rule set that generated the root. |
| `detected_at` | First and only persisted detection time. |

`is_valid_spirit_root` enforces one-dimensional canonical element order, no
NULL/duplicate/unknown elements, quality cardinality, non-variant NULL rules,
and the nine currently supported base/variant combinations.

The first migration does not invent cultivation rate or breakthrough-potential
columns before those rules exist in the current domain model. `generator_version`
preserves the birth rule set. A later additive cultivation migration may freeze
base numeric snapshots after their semantics and version mapping are approved.

### 4.5 `life_quest_states`

Quest-owned aggregate version per life. This is not objective progress.

```sql
CREATE TABLE life_quest_states (
    life_id       UUID PRIMARY KEY
                  REFERENCES lives(life_id) ON DELETE RESTRICT,
    revision      BIGINT NOT NULL DEFAULT 0 CHECK (revision >= 0),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

| Column | Meaning |
|---|---|
| `life_id` | Life whose quest aggregate is versioned. |
| `revision` | Monotonic quest-fact revision; increments only on real progress changes. |
| `updated_at` | Last real quest-state change time. |

The Quest repository lazily inserts revision 0 when first needed. It never uses
`MAX(quest_progress.revision) + 1`, which is unsafe under concurrent mutations.

### 4.6 `quest_progress`

Persisted quest facts. Derived presentation states and objective projections are
not stored.

```sql
CREATE TABLE quest_progress (
    life_id             UUID NOT NULL
                        REFERENCES lives(life_id) ON DELETE RESTRICT,
    quest_id            VARCHAR(128) NOT NULL,
    definition_version  INTEGER NOT NULL CHECK (definition_version > 0),
    status              VARCHAR(20) NOT NULL,
    accepted_at         TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ NULL,
    revision            BIGINT NOT NULL CHECK (revision > 0),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (life_id, quest_id),
    CONSTRAINT ck_quest_progress_status CHECK (status IN ('active', 'completed')),
    CONSTRAINT ck_quest_progress_completion CHECK (
        (status = 'active' AND completed_at IS NULL)
        OR
        (status = 'completed' AND completed_at IS NOT NULL)
    ),
    CONSTRAINT ck_quest_progress_time_order CHECK (
        completed_at IS NULL OR completed_at >= accepted_at
    )
);

CREATE INDEX ix_quest_progress_active_life
    ON quest_progress (life_id)
    WHERE status = 'active';

CREATE INDEX ix_quest_progress_revision
    ON quest_progress (life_id, revision);

CREATE FUNCTION prevent_quest_progress_reversal_or_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'quest progress rows are not deleted';
    END IF;
    IF OLD.life_id IS DISTINCT FROM NEW.life_id
       OR OLD.quest_id IS DISTINCT FROM NEW.quest_id
       OR OLD.definition_version IS DISTINCT FROM NEW.definition_version
       OR OLD.accepted_at IS DISTINCT FROM NEW.accepted_at THEN
        RAISE EXCEPTION 'quest progress identity and acceptance facts are immutable';
    END IF;
    IF NOT (OLD.status = 'active' AND NEW.status = 'completed') THEN
        RAISE EXCEPTION 'quest progress only transitions active to completed';
    END IF;
    IF NEW.revision <= OLD.revision THEN
        RAISE EXCEPTION 'quest progress revision must advance';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_quest_progress_prevent_reversal_delete
BEFORE UPDATE OR DELETE ON quest_progress
FOR EACH ROW EXECUTE FUNCTION prevent_quest_progress_reversal_or_delete();
```

| Column | Meaning |
|---|---|
| `life_id` | Life that owns the progress; quests do not carry across lives. |
| `quest_id` | Stable code-owned/content-owned quest ID. |
| `definition_version` | Quest definition version accepted by this life. |
| `status` | Durable fact: `active` or `completed`. |
| `accepted_at` | Successful acceptance time. |
| `completed_at` | Successful turn-in time. |
| `revision` | Aggregate quest revision assigned to this mutation. |
| `updated_at` | Last row update time. |

Quest definitions remain in version-controlled code/content files. There is no
foreign key to a quest-definition table. A future online content system may add
versioned definition storage without changing historical progress identity.

The current code-owned catalog exposes one active definition version per quest.
Because there is no production player data yet, incompatible definition changes
may reset or explicitly migrate the development database instead of retaining
old code paths. `definition_version` is persisted so mismatches fail fast and a
future content-publishing system can introduce version retention before public
operations. This slice does not implement a multi-version catalog.

The following values are derived, never persisted:

* `unavailable` and `available`;
* `ready_to_turn_in`;
* objective current/required/completed projections;
* provider action and dialogue key;
* tracked-quest UI state.

### 4.7 `quest_operations`

Compact technical idempotency ledger. It prevents duplicate accept/turn-in
effects caused by double-clicks, timeouts, and Adapter retries. It is not a
security identity table, gameplay analytics source, or player-history archive.

```sql
CREATE TABLE quest_operations (
    operation_id         UUID PRIMARY KEY,
    account_id           UUID NOT NULL
                         REFERENCES accounts(account_id) ON DELETE RESTRICT,
    life_id              UUID NOT NULL,
    command              VARCHAR(20) NOT NULL,
    quest_id             VARCHAR(128) NOT NULL,
    provider_id          VARCHAR(128) NOT NULL,
    request_fingerprint  VARCHAR(64) NOT NULL,
    state                VARCHAR(20) NOT NULL,
    changed              BOOLEAN NULL,
    response_status      SMALLINT NULL,
    response_content_type VARCHAR(64) NULL,
    response_body        BYTEA NULL,
    response_contract_version SMALLINT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    finalized_at         TIMESTAMPTZ NULL,
    CONSTRAINT fk_quest_operation_life_account
        FOREIGN KEY (life_id, account_id)
        REFERENCES lives(life_id, account_id) ON DELETE RESTRICT,
    CONSTRAINT ck_quest_operation_command CHECK (command IN ('accept', 'turn_in')),
    CONSTRAINT ck_quest_operation_fingerprint CHECK (
        request_fingerprint ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_quest_operation_state CHECK (
        state IN ('processing', 'succeeded', 'domain_failed')
    ),
    CONSTRAINT ck_quest_operation_content_type CHECK (
        response_content_type IS NULL
        OR response_content_type = 'application/json'
    ),
    CONSTRAINT ck_quest_operation_finalization CHECK ((
        (state = 'processing'
            AND changed IS NULL
            AND response_status IS NULL
            AND response_content_type IS NULL
            AND response_body IS NULL
            AND response_contract_version IS NULL
            AND finalized_at IS NULL)
        OR
        (state = 'succeeded'
            AND changed IS NOT NULL
            AND response_status IS NOT NULL
            AND response_status BETWEEN 200 AND 299
            AND response_content_type IS NOT NULL
            AND response_body IS NOT NULL
            AND response_contract_version IS NOT NULL
            AND finalized_at IS NOT NULL)
        OR
        (state = 'domain_failed'
            AND changed IS FALSE
            AND response_status IS NOT NULL
            AND response_status BETWEEN 400 AND 499
            AND response_content_type IS NOT NULL
            AND response_body IS NOT NULL
            AND response_contract_version IS NOT NULL
            AND finalized_at IS NOT NULL)
    ) IS TRUE)
);

CREATE INDEX ix_quest_operations_account_created
    ON quest_operations (account_id, created_at DESC);

CREATE FUNCTION prevent_quest_operation_rewrite_or_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'quest operation rows are not deleted';
    END IF;
    IF OLD.state <> 'processing' THEN
        RAISE EXCEPTION 'finalized quest operations are immutable';
    END IF;
    IF OLD.operation_id IS DISTINCT FROM NEW.operation_id
       OR OLD.account_id IS DISTINCT FROM NEW.account_id
       OR OLD.life_id IS DISTINCT FROM NEW.life_id
       OR OLD.command IS DISTINCT FROM NEW.command
       OR OLD.quest_id IS DISTINCT FROM NEW.quest_id
       OR OLD.provider_id IS DISTINCT FROM NEW.provider_id
       OR OLD.request_fingerprint IS DISTINCT FROM NEW.request_fingerprint
       OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
        RAISE EXCEPTION 'quest operation request identity is immutable';
    END IF;
    IF NEW.state NOT IN ('succeeded', 'domain_failed') THEN
        RAISE EXCEPTION 'quest operation must finalize in one update';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_quest_operations_prevent_rewrite_delete
BEFORE UPDATE OR DELETE ON quest_operations
FOR EACH ROW EXECUTE FUNCTION prevent_quest_operation_rewrite_or_delete();
```

| Column | Meaning |
|---|---|
| `operation_id` | Globally unique Adapter-generated request ID. |
| `account_id` | Account that issued the operation. |
| `life_id` | Actual life affected by the original operation. |
| `command` | `accept` or `turn_in`. |
| `quest_id` | Mutation target. |
| `provider_id` | Provider/NPC context. |
| `request_fingerprint` | SHA-256 fingerprint of the canonical request identity. |
| `state` | Transaction-local `processing`, or finalized success/domain failure. |
| `changed` | Whether the operation created/completed progress. |
| `response_status` | Frozen HTTP status. |
| `response_content_type` | Frozen response media type, initially `application/json`. |
| `response_body` | Frozen success/error wire bytes; replay never parses or reserializes them. |
| `response_contract_version` | Version of the frozen response contract. |
| `created_at` | First operation creation time. |
| `finalized_at` | Time the replayable result was frozen. |

There is no operation archive table, lease, worker owner, retry counter, or
mutation recovery snapshot in this slice.

The request fingerprint is lowercase SHA-256 over canonical JSON containing
`contract_version`, `account_id`, `command`, `quest_id`, and `provider_id`.

Quest mutation use cases return a small application-layer `FrozenHttpResponse`
value containing status, content type, and body bytes. A newly produced success
or domain failure is serialized once, frozen in this row, committed, and then
returned. A replay returns the stored bytes directly through a Starlette
`Response`; it does not rebuild a Pydantic model or raise a domain exception for
FastAPI to serialize again. Validation errors before operation reservation and
unexpected 5xx failures are not frozen.

The entire operation runs in one short database transaction. Reservation uses:

```sql
INSERT INTO quest_operations (..., state)
VALUES (..., 'processing')
ON CONFLICT (operation_id) DO NOTHING
RETURNING operation_id;
```

Returning a row means this transaction owns the new operation. Returning no row
means another committed/concurrent operation owns the ID; after the conflicting
transaction resolves, the repository loads it and compares account, command,
quest, provider, and fingerprint before replaying or returning a conflict. It
does not catch a plain unique-violation and continue in an aborted transaction.

* Crash before commit: operation, progress, and revision all roll back.
* Retry after rollback: executes normally.
* Retry after commit: compares command/quest/provider/fingerprint and replays the
  frozen response.
* Same operation ID with a different request identity: idempotency conflict.
* A retry after reincarnation still finds the globally keyed original operation
  and replays its old-life result instead of rebinding to the new life.

Rows are retained initially. Actual scale and support requirements, not an
assumed archive policy, determine any later pruning or partition design.

## 5. Quest Projection

The Quest service loads, in one consistent database snapshot:

1. current alive life and player revision;
2. immutable spirit-root presence/facts;
3. `life_quest_states.revision`;
4. `quest_progress` rows required by the requested providers;
5. code-owned quest/provider definitions and their catalog revision.

It derives states as follows:

| Progress fact | Prerequisites/objectives | Projection |
|---|---|---|
| no row | prerequisites incomplete | `unavailable` |
| no row | prerequisites complete | `available` |
| `active` | objectives incomplete | `active` |
| `active` | objectives complete | `ready_to_turn_in` |
| `completed` | ignored | `completed` |

The response revision vector contains player, quest, and definition revisions.

Future objective types implement explicit evaluators against authoritative
module service contracts:

```text
CURRENT_LIFE_SPIRIT_ROOT_PRESENT -> Player/Cultivation facts
KILL_MOB                        -> Combat facts/projection
COLLECT_ITEM                    -> Item facts/projection
DIALOGUE_CHOICE                 -> Narrative facts/projection
```

Quest does not bypass module services to query another module's tables, and it
does not persist a second mutable counter when a fact is derivable elsewhere.

Projection runs inside one shared async Unit of Work using a SQLAlchemy
`AsyncSession` opened at PostgreSQL `REPEATABLE READ`. Player fact readers and Quest
repositories are bound to that same session. A module service exposes facts
through its contract but does not open an independent transaction.

## 6. Transaction Flows

### 6.1 Login and current-life creation

1. Upsert `accounts` by Minecraft UUID and return the account row.
2. Upsert the account/name observation.
3. Lock the returned account row with `SELECT ... FOR UPDATE`.
4. Query the partial alive-life index.
5. If no life exists and the account has no historical life, insert generation
   1. If historical rows exist without an alive life, return an explicit
   lifecycle error; login must not bypass future reincarnation orchestration.
6. The partial unique index is the final concurrency guard. A serialization or
   unique conflict retries the whole short login transaction once.
7. Return account and current life.

Player name is display/audit data only. No lookup or ownership decision uses it
as identity.

### 6.2 Spirit-root detection

1. Lock the current alive life row.
2. If `life_spirit_roots` already exists, return it with `already_detected=true`.
3. Generate one root using the current versioned generator.
4. Insert the immutable root row.
5. Increment `lives.revision` atomically.
6. Commit and return the created root.

The one-to-one primary key and life lock guarantee that concurrent detection
requests cannot produce two roots.

### 6.3 Quest accept/turn-in

1. Begin a short transaction.
2. Look up the global operation ID first. A finalized match replays even if the
   account has since entered another life.
3. For a new operation, lock the account and resolve/lock its current alive life.
4. Recheck the operation ID after acquiring the account lock, then reserve it
   with `INSERT ... ON CONFLICT DO NOTHING RETURNING` as the final race guard.
5. Lock/lazily create `life_quest_states`.
6. Read current-life facts and relevant progress through readers bound to the
   same Unit of Work.
7. Validate provider, current definition version, prerequisites, objective facts,
   and current progress.
8. Apply the conditional insert or `active -> completed` update. If the
   conditional write returns no row, reload the locked progress: an already
   active/completed accept or completed turn-in is a successful no-op with
   `changed=false`; invalid states become frozen domain failures.
9. Increment quest revision only when the durable state changed.
10. Build the response from the post-mutation snapshot.
11. Finalize the operation with frozen success or domain-failure wire bytes.
12. Commit normally, then return the exact frozen status, content type, and body
    bytes for both success and domain failure.

No network call, Paper API, Citizens API, or long-running calculation may occur
inside this transaction.

The global lock order for player/quest mutations is `accounts`, `lives`,
operation reservation, `life_quest_states`, and finally `quest_progress`. Code
that does not require an earlier lock must not acquire it later out of order.

## 7. Future Life Aggregate

The old Mortals `players` columns are treated as per-life vocabulary, not copied
into one wide row.

| Future table/module | Life-owned concepts |
|---|---|
| `life_cultivation_states` | realm/stage code, realized cultivation, unrefined cultivation, pill poison, heart demon, revision |
| `cultivation_resource_entries` | append-only combat reward, reserve consumption, and realized-cultivation ledger |
| `cultivation_sessions` | selected technique, eligible zone, offline-effective seclusion, settlement cursors |
| `life_cultivation_effects` | permanent-life, timed, and next-action modifiers |
| `life_vitality_states` | age/lifespan facts and future vitality state |
| `life_techniques` | per-life learned/equipped technique progression |
| `life_sect_memberships` | stable sect/position IDs and membership history |
| Item-owned inventory/equipment tables | item instances, ownership, equipment, provenance, loot pools |
| Party/social tables | team identity and membership; never embedded as `team_id/is_leader` flags on `lives` |
| World/travel tables | semantic zones/travel only; Paper owns physical Minecraft presentation/location |
| `life_statistics` | derived/materialized life metrics where real query pressure justifies them |

Definition-derived values such as realm name and required experience stay in
version-controlled content. They are not duplicated as `level`/`max_exp` player
columns.

## 8. Combat Cultivation and Offline Seclusion

Minecraft combat does not directly advance the realm bar.

```text
authoritative combat reward
    -> credit current life's unrefined cultivation
    -> player travels to an eligible cultivation area
    -> player selects a learned/compatible technique
    -> start persisted seclusion session
    -> online/offline settlement consumes reserve
    -> credit realized cultivation/realm progress
```

The old idle-travel/exploration mode is removed. World travel is active
Minecraft gameplay; only seclusion has offline progression semantics.

Time-to-realm targets, hourly rates, and final duration formulas are explicitly
deferred. The schema only preserves the necessary distinction and settlement
cursor.

Future authoritative ledgers use stable source event IDs so combat retries
cannot duplicate cultivation rewards. Technical `quest_operations` rows are not
gameplay analytics and are never counted as player activity.

## 9. Cultivation Base Values and Effects

When cultivation is implemented, spirit-root base rate and breakthrough
potential/chance semantics are introduced by an additive migration and frozen as
immutable snapshots. Effective values are deterministic Cultivation-service
calculations using fixed-point units.

Future `life_cultivation_effects` supports exactly three lifetimes:

* `permanent_life`;
* `timed`;
* `next_action`.

Each effect records stat code, modifier type/value, source type/ID, optional item
instance, stack key, remaining uses, start/expiry/consumption timestamps, and
status. It does not overwrite the spirit-root row.

The old Mortals values are playtest seeds, not a copied balance contract:

* relative root rates around 0.7x, 1.0x, 1.8x, and 2.0x;
* ordinary cultivation pills around +10% success and 1.15x rate;
* rare examples up to +40% success and 1.50x rate;
* pill-poison and failure penalties retained as concepts but recalibrated for
  Minecraft session pacing.

Authoritative probabilities and rates use integer basis points, not floats.

## 10. Cross-Life Inheritance

### 10.1 Technique marks

Future storage uses:

```text
account_technique_marks  -> current aggregate layer count
technique_mark_events    -> append-only grant history
```

One technique may grant at most one layer per life. The same technique may grant
another layer after being mastered in a later life. A unique
`(source_life_id, technique_id)` constraint prevents duplicate settlement.

The total layer cap belongs to the versioned technique definition, not the
account-row schema.

### 10.2 Inherited items

Future inherited items become provenance-bearing account entitlements with
states such as `sealed`, `eligible`, `claimed`, and `consumed`. They record the
origin life/item, unlock rule version, conditions, eligible generation, and
claiming life.

A new life does not automatically receive a copied item row.

## 11. Player History, Recaps, and Analytics

Historical lives remain in the same domain tables with terminal status. This
keeps foreign keys valid and makes reincarnation atomic; it avoids moving every
root, quest, item, and future cultivation row between active/archive schemas.

Current-life queries use the small partial alive index. Historical queries use
`(account_id, generation_no)`. Physical partitioning is considered only after
measured scale justifies it.

Future product-facing recaps use separate read models:

```text
life_recap_snapshots
player_activity_events
annual_player_reports
```

Meaningful domain facts include cultivation sessions, breakthroughs, completed
quests, boss kills, rare-item acquisition, sect milestones, deaths, and
reincarnation. Request retry/idempotency data is never used as gameplay
analytics.

Large recap queries run against materialized views, a read replica, or a future
analytics store rather than the login/transaction path.

## 12. SQLAlchemy, Alembic, and Application Composition

* Use SQLAlchemy 2.x typed models and async repository implementations.
* Use asyncpg through SQLAlchemy's async engine.
* Use Alembic for deterministic named migrations.
* Never edit an applied migration; add expand/contract migrations.
* Structural migrations and demo/content seeding remain separate.
* Application composition builds one shared async database/session factory and
  injects PostgreSQL repositories into PlayerService and QuestService.
* Each API use case opens a shared async Unit of Work/Session and passes transaction-
  bound repositories/readers through the service boundary.
* Existing synchronous service/repository contracts are replaced directly; no
  sync bridge, deprecation wrapper, or dual-mode code remains.
* Route handlers do not execute SQL.
* Cross-module orchestration uses explicit services/unit-of-work boundaries;
  repositories do not reach into tables owned by another module.
* Database migrations run as an explicit deployment step, not automatically on
  every application startup.

## 13. Operational Requirements

* Configure pool size and timeouts explicitly; do not accept driver defaults as
  production policy.
* Readiness verifies database connectivity and expected migration revision.
* Structured logs include account/life/operation IDs where safe, without logging
  full private payloads.
* Monitor pool saturation, transaction latency, lock waits, operation conflicts,
  migration revision, and repository error rates.
* Before storing operational player data, enable automated backups and WAL/PITR
  appropriate to the deployment environment.
* A backup is not accepted until a real restore into an isolated database has
  succeeded.
* Dangerous migrations require a fresh recovery point and rehearsal against a
  recent production-like snapshot.

## 14. Testing

### Migration tests

* upgrade an empty database to head;
* upgrade a previous-revision fixture to head;
* verify named constraints and indexes;
* verify downgrade where it is safe and supported.

### Player repository tests

* concurrent first login creates one account and one alive life;
* name changes update current display and preserve observations;
* a second alive life is rejected;
* ordinary death does not terminate a life;
* terminal transition is one-way and internally consistent;
* concurrent spirit-root detection creates one immutable result;
* root quality/element constraints reject invalid rows;
* restart returns the same account, life, and spirit root.

### Quest repository/service tests

* progress is isolated by life;
* concurrent accept produces one durable state change;
* concurrent turn-in completes exactly once;
* aggregate revision increments only on real change;
* duplicate operation replays the exact frozen success/error;
* operation ID reuse with another request conflicts;
* transaction failure leaves no progress without a corresponding operation;
* restart preserves progress, revisions, and idempotency behavior;
* derived available/ready states remain consistent with authoritative facts.

### Performance checks

* login/current-life lookup uses the partial alive index;
* provider inspection performs a bounded number of aggregate queries;
* no N+1 query per quest/objective;
* mutation transactions contain no network or Paper work;
* lock-wait and transaction latency are measured under concurrent retries.

## 15. Rollout and Rollback

The current durable store is empty because production data is still in-memory.
There is no legacy data migration in this slice.

Rollout sequence:

1. provision PostgreSQL and credentials;
2. run Alembic migrations explicitly;
3. verify migration revision and repository integration tests;
4. start Game Service with PostgreSQL repositories;
5. run login, spirit-root, quest accept/turn-in, restart, and replay smoke tests;
6. only then treat the environment as retaining player data.

Rollback favors application rollback while retaining additive schema. A
destructive downgrade is not used after accepting player writes unless its data
loss has been explicitly rehearsed and approved. Restore-from-backup is the
rollback path for destructive corruption.

## 16. Explicitly Out of Scope

* importing QQ bot players;
* online quest editing or quest-definition database tables;
* generic persisted objective counters;
* implementing cultivation, seclusion, sect, item, combat, market, dungeon,
  PVP, inherited-item, recap, or analytics tables in the first migration;
* choosing final cultivation timing or time-to-realm targets;
* Redis coordination or multi-server distribution;
* changing Paper/Citizens authoring behavior.

## 17. Acceptance Criteria

* PostgreSQL restart preserves account, current life, spirit root, quest progress,
  quest revision, and idempotency outcomes.
* Database constraints enforce one current life, one root per life, one progress
  row per life/quest, and one globally unique request identity per operation.
* Duplicate/retried quest mutations cannot grant state twice.
* Current-life reads remain index-isolated from historical generations.
* The schema has no permanent QQ compatibility fields and no silent in-memory
  production fallback.
* Obsolete synchronous contracts, lease/waiter operation code, and their tests
  are removed rather than retained behind compatibility adapters.
* Future life-owned systems and allowlisted cross-life inheritance have explicit
  module boundaries without speculative first-migration tables.
* Migration, concurrency, restart, and repository integration checks pass.

## 18. References

* `architecture-v2.md`
* `game-design-reincarnation-inheritance.md`
* `.trellis/spec/backend/database-guidelines.md`
* `docs/superpowers/specs/2026-07-13-custom-quest-vertical-slice-design.md`
* `.trellis/tasks/07-14-postgresql-schema-design/prd.md`
* `.trellis/tasks/07-14-postgresql-schema-design/research/mortals-numeric-design-reference.md`
* `/home/adam/projects/mortals/init_db.py`
