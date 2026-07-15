# MythicMobs Kill Cultivation Rewards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline execution is selected for this session). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a durable MythicMobs player-kill pipeline that attributes the lethal player-owned damage source, persists compact combat/count facts, and credits current-life unrefined cultivation exactly once.

**Architecture:** Paper captures typed MythicMobs death facts and tracks lethal damage ownership locally. A SQLite WAL outbox commits captures synchronously, then an asynchronous scheduled worker sends bounded batches to Game Service. Game Service validates the source-life claim, resolves the current life, calculates rewards from its catalog, and atomically writes PostgreSQL combat facts, counters, cultivation ledger entries, and reserve balance.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, PostgreSQL/asyncpg, pytest; Java 21, Paper API 1.21.11, Mythic-Dist 5.12.1 compile-only, Jackson, Xerial SQLite JDBC, JUnit 5, Gradle.

---

## File Map

Game Service files are split by domain responsibility:

- Create `game-service/src/immortal_mmo/combat/models.py` for immutable kill/source/result domain values.
- Create `game-service/src/immortal_mmo/combat/catalog.py` for validated versioned Mythic reward/telemetry definitions and checked reward calculation.
- Create `game-service/src/immortal_mmo/combat/schemas.py` for batch HTTP request/response models.
- Create `game-service/src/immortal_mmo/combat/db_models.py` for combat-event and kill-counter SQLAlchemy rows.
- Create `game-service/src/immortal_mmo/cultivation/db_models.py` for cultivation aggregate and ledger rows.
- Create `game-service/src/immortal_mmo/combat/repository.py` / `postgres_repository.py` and `cultivation/repository.py` / `postgres_repository.py` for session-bound module-owned writes/reads.
- Create `game-service/src/immortal_mmo/combat/service.py` for transaction orchestration and idempotent per-event outcomes.
- Create `game-service/src/immortal_mmo/combat/api.py` and update `game-service/src/immortal_mmo/api/v1/router.py` for the batch endpoint.
- Create `game-service/migrations/versions/20260715_002_combat_cultivation_rewards.py` for the additive schema.
- Update `game-service/src/immortal_mmo/db/uow.py`, `main.py`, and `entrypoint.py` to expose a session-bound combat repository without opening nested transactions.
- Create focused Python tests under `game-service/tests/unit/test_combat_catalog.py`, `test_combat_service.py`, `test_combat_schemas.py`, and integration tests under `game-service/tests/integration/test_combat_api.py`, `test_combat_postgres_repository.py`, and `test_combat_migrations.py`.

Paper files are split into integration, attribution, outbox, and client layers:

- Update `minecraft-nodes/main-plugin/build.gradle.kts` with compile-only Mythic-Dist 5.12.1, runtime/library Xerial SQLite JDBC, and test dependencies.
- Update `minecraft-nodes/main-plugin/src/main/resources/plugin.yml` with MythicMobs soft-dependency and any library declarations required by the verified Paper loader.
- Update `minecraft-nodes/main-plugin/src/main/resources/config.yml` with `server-id`, outbox intervals/batch limits, high-load threshold, pending-age guard, and attribution limits.
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/combat/CombatSource.java`, `CombatAttributionTracker.java`, `CombatAttributionKind.java`, `BukkitCombatAttributionListener.java`, and tests for direct/projectile/DoT/summon/trap/formation attribution and source-life isolation.
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/mythicmobs/MythicMobsIntegrationLoader.java`, `MythicMobDeathListener.java`, `MythicMobDeathSnapshot.java`, and tests for missing/incompatible/present MythicMobs.
- Create `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/SqliteKillOutbox.java`, `KillOutboxRow.java`, `OutboxDeliveryWorker.java`, `OutboxDeliveryPolicy.java`, and tests for WAL/FULL setup, leases, retries, batching, dead letters, and restart recovery.
- Extend `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/GameServiceClient.java` with batch kill delivery and create `CombatKillEventRequest.java`, `CombatKillBatchRequest.java`, `CombatKillBatchResponse.java`, and per-event result types.
- Update `ImmortalMainPlugin.java` to initialize the tracker, SQLite outbox, scheduler, client batch sender, and optional MythicMobs listener; shut them down in reverse order.

The existing player/quest transaction patterns, `PostgresPlayerRepository`, `SqlAlchemyUnitOfWork`, Jackson naming strategy, and Citizens optional-loader pattern are the implementation references.

## Task 1: Establish domain contracts and failing tests

**Files:**
- Create: `game-service/src/immortal_mmo/combat/models.py`
- Create: `game-service/src/immortal_mmo/combat/catalog.py`
- Create: `game-service/src/immortal_mmo/combat/schemas.py`
- Test: `game-service/tests/unit/test_combat_catalog.py`
- Test: `game-service/tests/unit/test_combat_schemas.py`

- [x] **Step 1: Add failing catalog tests** for exact internal-name lookup, unknown IDs returning `not_rewardable`, compact/detailed telemetry, decimal level bounds, deterministic integer reward output, and overflow rejection.
- [x] **Step 2: Add failing schema tests** for batch requests capped by configured size, decimal-string mob levels, UUID validation, attribution kinds, optional source-life/technique/cast fields, and per-event result decoding.
- [x] **Step 3: Implement frozen domain values** with explicit literals:

  ```python
  AttributionKind = Literal[
      "direct", "projectile", "damage_over_time", "summon",
      "trap", "formation",
  ]
  TerminalOutcome = Literal[
      "accepted", "duplicate", "not_rewardable",
      "account_not_found", "current_life_unavailable",
  ]
  ```

  Use `Decimal` for mob levels and checked integer arithmetic for reward amounts. Keep the adapter amount-free: the request models contain no reward field.
- [x] **Step 4: Implement catalog loading** from a version-controlled YAML/JSON content file with duplicate-ID, profile, curve, telemetry, level-bound, and overflow validation. A missing/invalid catalog raises a startup error; an unknown mob ID has an explicit terminal result rather than a default amount.
- [x] **Step 5: Run focused tests**:

  ```bash
  cd game-service && uv run pytest tests/unit/test_combat_catalog.py tests/unit/test_combat_schemas.py -q
  ```

  Expected: all new tests pass.
- [x] **Step 6: Commit** `feat: add combat reward domain contracts`.

## Task 2: Add PostgreSQL schema and persistence rows

**Files:**
- Create: `game-service/migrations/versions/20260715_002_combat_cultivation_rewards.py`
- Create: `game-service/src/immortal_mmo/combat/db_models.py`
- Create: `game-service/src/immortal_mmo/combat/repository.py`
- Create: `game-service/src/immortal_mmo/combat/postgres_repository.py`
- Modify: `game-service/src/immortal_mmo/db/uow.py`
- Test: `game-service/tests/integration/test_combat_migrations.py`
- Test: `game-service/tests/integration/test_combat_postgres_repository.py`

- [x] **Step 1: Write migration tests** asserting creation of `life_cultivation_states`, `combat_kill_events`, `life_mob_kill_counters`, and `cultivation_resource_entries`; check source uniqueness, attribution/outcome constraints, compact/detail payload shape, and partial combat-reward uniqueness.
- [x] **Step 2: Write repository tests** for source reservation, immutable replay load, current-life lock, counter upsert, cultivation-state creation/update, reward-ledger insertion, and rollback behavior.
- [x] **Step 3: Implement the Alembic migration** exactly as the approved design: UUID identities, `NUMERIC(12,3)` level, source-life/account/life references with `RESTRICT`, append-only combat row, counter primary key, reserve state, and partial unique index `(kill_event_id, life_id, resource_code) WHERE entry_type='combat_reward'`.
- [x] **Step 4: Implement typed SQLAlchemy rows** with `Mapped` annotations and naming/constraint conventions matching `player/db_models.py`; do not add cascade deletes or localized text columns.
- [x] **Step 5: Implement session-bound Combat and Cultivation repositories** with methods for:

  ```python
  reserve_or_load_source(session, source_event_id, immutable_fingerprint)
  lock_account_by_minecraft_uuid(session, killer_uuid)
  lock_current_life(session, account_id)
  insert_kill_event(session, event)
  increment_mob_counter(session, life_id, mob_id, occurred_at)
  lock_or_create_cultivation_state(session, life_id)
  append_reward_entry_and_increment_reserve(
      session,
      life_id,
      kill_event_id,
      reward_amount,
      occurred_at,
  )
  ```

  Unique conflicts must roll back/retry the short transaction; never continue using an aborted SQLAlchemy transaction.
- [x] **Step 6: Expose `combat` and `cultivation` from `SqlAlchemyUnitOfWork`** using the same session and isolation level as player/quest repositories. Update factories in `entrypoint.py` and composition tests.
- [x] **Step 7: Run migration/repository tests**:

  ```bash
  cd game-service && uv run pytest tests/integration/test_combat_migrations.py tests/integration/test_combat_postgres_repository.py -q
  ```

  Expected: PostgreSQL migration, constraints, locks, and rollback tests pass.
- [x] **Step 8: Commit** `feat: persist combat kills and cultivation reserve`.

## Task 3: Implement Game Service transaction and batch API

**Files:**
- Create: `game-service/src/immortal_mmo/combat/service.py`
- Create: `game-service/src/immortal_mmo/combat/api.py`
- Modify: `game-service/src/immortal_mmo/api/v1/router.py`
- Modify: `game-service/src/immortal_mmo/main.py`
- Test: `game-service/tests/unit/test_combat_service.py`
- Test: `game-service/tests/integration/test_combat_api.py`

- [x] **Step 1: Write service tests** for accepted reward, exact duplicate replay, mismatched identity conflict, unknown catalog ID, missing account, missing current life, stale source-life mismatch, lethal attribution fields, counter increment, reserve increment, and atomic rollback.
- [x] **Step 2: Implement `CombatRewardService.process_batch()`** with a bounded event loop. For each event: begin a short UoW transaction, load an existing frozen result before consulting the current catalog, validate catalog for new events, lock account/current life, validate source-life claim, calculate reward, insert immutable event, increment counter/state, append ledger, commit, and return the frozen result. A valid terminal no-reward outcome is committed and acknowledged.
- [x] **Step 3: Add the endpoint** `POST /api/v1/combat/mythicmob-kills/batch`. Accept `{contract_version, events[]}`; return HTTP 200 with one result per input event. Return 429/503/5xx for whole-batch service overload/failure; return stable per-event terminal outcomes for valid domain decisions. Reject missing/duplicate/reassigned result IDs in the adapter.
- [x] **Step 4: Wire the service into `create_app()`** and runtime composition. Keep all database work async and keep HTTP/Paper APIs outside PostgreSQL transactions.
- [x] **Step 5: Run API/service tests**:

  ```bash
  cd game-service && uv run pytest tests/unit/test_combat_service.py tests/integration/test_combat_api.py -q
  ```

  Expected: idempotency, life isolation, batch response, and error classification tests pass.
- [x] **Step 6: Commit** `feat: expose idempotent combat reward batch API`.

## Task 4: Add Paper combat attribution contracts

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/combat/CombatAttributionKind.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/combat/CombatSource.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/combat/CombatAttributionTracker.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/combat/CombatAttributionTrackerTest.java`

- [x] **Step 1: Write failing Java tests** for direct player damage, projectile shooter, DoT owner propagation, summon/trap/formation owner propagation, lethal-source selection, cancelled-damage exclusion, source-life mismatch metadata, expiry, max-target eviction, despawn cleanup, and ambiguous post-restart damage returning no attribution.
- [x] **Step 2: Implement immutable `CombatSource`** with `playerUuid`, optional `sourceLifeId`, optional `techniqueId`, optional `castId`, attribution kind, and expiry. Require non-null player UUID and validate source age at construction.
- [x] **Step 3: Implement tracker operations**:

  ```java
  void recordDamage(UUID target, CombatSource source, double finalDamage, boolean lethal, Instant at);
  Optional<LethalAttribution> consumeLethal(UUID target, Instant at);
  void clear(UUID target);
  void clearAll();
  ```

  Keep a bounded map keyed by target entity UUID. A dedicated final-priority Bukkit listener records ordinary player melee as `direct` and player-owned projectiles as `projectile`. Custom DoT/summon/trap/formation damage must enter through the shared source gateway. If no tracked source exists at death, return no attribution; never reconstruct ownership from `getKiller()`.
- [x] **Step 4: Run Java combat tests**:

  ```bash
  cd minecraft-nodes/main-plugin && ./gradlew test --tests '*CombatAttributionTrackerTest'
  ```

  Expected: all source-kind and lifecycle tests pass.
- [x] **Step 5: Commit** `feat: attribute lethal combat sources`.

## Task 5: Add MythicMobs typed integration

**Files:**
- Modify: `minecraft-nodes/main-plugin/build.gradle.kts`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/plugin.yml`
- Modify: `minecraft-nodes/main-plugin/src/main/resources/config.yml`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/mythicmobs/MythicMobsIntegrationLoader.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/mythicmobs/MythicMobDeathSnapshot.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/mythicmobs/MythicMobDeathListener.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/mythicmobs/MythicMobDeathListenerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/mythicmobs/MythicMobsIntegrationLoaderTest.java`

- [x] **Step 1: Add compile-only Mythic-Dist 5.12.1** from the official Maven repository and add Xerial SQLite JDBC through the verified Paper library mechanism. Do not shade MythicMobs or include Premium jars.
- [x] **Step 2: Add `softdepend: [Citizens, MythicMobs]` and explicit config defaults** for server ID, attribution limits, delivery cadence, batch limits, and max pending age.
- [x] **Step 3: Write listener tests** using adapter-owned immutable fixtures for exact internal name, mob level, entity UUID, world, coordinates, source mapping, stable event ID, missing-attribution filtering, and incompatible/missing plugin states.
- [x] **Step 4: Implement the optional loader** following the Citizens integration pattern. Class loading of Mythic-linked types occurs only inside the enabled integration path. Missing MythicMobs logs unavailable; incompatible linkage fails startup visibly with no generic entity fallback.
- [x] **Step 5: Implement `MythicMobDeathListener`** on the Paper thread: read `MythicMobDeathEvent`, consume required lethal attribution, skip and diagnose deaths with no tracked source, build a compact immutable request with source-life/technique/cast metadata, and hand it to the durable outbox. Never calculate a reward or perform network work here.
- [x] **Step 6: Run integration tests**:

  ```bash
  cd minecraft-nodes/main-plugin && ./gradlew test --tests '*MythicMobDeath*' --tests '*MythicMobsIntegrationLoaderTest'
  ```

  Expected: free API compile/test fixtures pass with MythicMobs absent/present paths.
- [x] **Step 7: Commit** `feat: capture MythicMobs death facts`.

## Task 6: Implement SQLite WAL outbox and scheduled batch delivery

**Files:**
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/KillOutboxRow.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/SqliteKillOutbox.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/OutboxDeliveryPolicy.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/outbox/OutboxDeliveryWorker.java`
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/GameServiceClient.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillEventRequest.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillBatchRequest.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillBatchResponse.java`
- Create: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/client/CombatKillResult.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/outbox/SqliteKillOutboxTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/outbox/OutboxDeliveryWorkerTest.java`
- Test: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/client/GameServiceClientCombatTest.java`

- [x] **Step 1: Write SQLite tests** for schema pragmas, synchronous durable insert, duplicate enqueue, bounded writer queue, lease claim/recovery, terminal delete, retry backoff, dead-letter transition, malformed row handling, checkpoint failure visibility, and restart replay.
- [x] **Step 2: Implement one-writer SQLite initialization** under `plugins/ImmortalMC/outbox.sqlite` with WAL, FULL, foreign keys, busy timeout, schema creation, and a bounded executor. `append()` returns success only after commit; it never performs HTTP.
- [x] **Step 3: Implement lease state transitions**:

  ```text
  pending -> in_flight(lease)
  in_flight(expired) -> pending
  in_flight(terminal) -> delete
  in_flight(retryable) -> pending(next_attempt_at)
  in_flight(invalid) -> dead_letter
  ```

  Use deterministic `event_id` conflict no-op and keep immutable payload fields unchanged on retry.
- [x] **Step 4: Extend `GameServiceClient`** with `/api/v1/combat/mythicmob-kills/batch`, configurable timeout, complete result-ID validation, HTTP classification, and JSON parsing. A whole-batch timeout is retryable; a 200 response missing or duplicating IDs is a local protocol failure/dead letter, never guessed.
- [x] **Step 5: Implement scheduled worker** with configurable normal/high-load intervals, TPS threshold, bounded batch size, `max-pending-age` override, exponential backoff/jitter, and one in-flight batch. Use `ScheduledExecutorService`, not OS cron or the Paper main scheduler.
- [x] **Step 6: Run outbox/client tests**:

  ```bash
  cd minecraft-nodes/main-plugin && ./gradlew test --tests '*SqliteKillOutboxTest' --tests '*OutboxDeliveryWorkerTest' --tests '*GameServiceClientCombatTest'
  ```

  Expected: no network operation occurs on the Paper thread; rows survive simulated restart and ambiguous batch timeout.
- [x] **Step 7: Commit** `feat: add durable SQLite combat outbox`.

## Task 7: Wire plugin lifecycle and end-to-end behavior

**Files:**
- Modify: `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/ImmortalMainPlugin.java`
- Modify: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/PluginResourceTest.java`
- Create/modify: `minecraft-nodes/main-plugin/src/test/java/com/immortalmc/adapter/ImmortalMainPluginIntegrationTest.java`
- Modify: `game-service/tests/integration/test_app_composition.py`
- Modify: `game-service/README.md`
- Modify: `minecraft-nodes/main-plugin/README.md`
- Modify: `minecraft-nodes/main-server/README.md`

- [x] **Step 1: Wire startup order**: settings → GameServiceClient → attribution tracker → SQLite outbox → delivery worker → optional MythicMobs loader/listener. Log server ID, integration availability, and outbox path without player payloads.
- [x] **Step 2: Wire shutdown order**: stop listener, stop scheduler, drain/close writer, checkpoint/close SQLite, then clear existing session/quest state. No new event may be accepted after outbox shutdown begins.
- [x] **Step 3: Add resource/config tests** for soft dependency, official free API version, default outbox settings, no Premium artifact references, and catalog content loading.
- [x] **Step 4: Document operator flow**: define a native MythicMobs mob key, add matching Game Service catalog entry, reload/restart both services, verify unknown-ID behavior, and inspect pending/dead-letter metrics.
- [x] **Step 5: Run full project checks**:

  ```bash
  cd game-service && uv run ruff check . && uv run pytest -q
  cd ../minecraft-nodes/main-plugin && ./gradlew test build
  ```

  Expected: Python tests, Java tests, and plugin build are green.
- [x] **Step 6: Commit** `feat: wire MythicMobs cultivation reward vertical slice`.

## Task 8: Real-server smoke, quality gate, and handoff

**Files:**
- Modify: `.trellis/tasks/07-15-mythicmob-cultivation-rewards/prd.md` acceptance checkboxes
- Modify: `.trellis/spec/backend/quality-guidelines.md` only if a reusable event-ingestion convention is discovered
- Create: `.trellis/tasks/07-15-mythicmob-cultivation-rewards/research/implementation-notes.md` for measured load/compatibility findings

- [ ] **Step 1: Start PostgreSQL, Game Service, and Paper with official free MythicMobs 5.12.1** using the existing scripts; do not copy Premium jars into the build or CI path.
- [ ] **Step 2: Configure one compact ordinary mob and one detailed Boss** using native MythicMobs YAML plus matching Game Service catalog IDs.
- [ ] **Step 3: Verify one direct kill, one projectile/DoT-owned kill, one unknown mob, and one source-life mismatch. Confirm counters, combat facts, ledger entries, and unrefined reserve.
- [ ] **Step 4: Stop Game Service, capture kills, restart Paper, restart Game Service, and verify outbox redelivery credits exactly once.
- [ ] **Step 5: Exercise high-load delivery configuration and confirm local capture remains immediate while HTTP cadence changes and max pending age is respected.
- [ ] **Step 6: Run `trellis-check`, fix all findings, update relevant backend specs if a reusable ingestion pattern emerged, and record measured findings.
- [ ] **Step 7: Push all commits and send the project completion notification after the quality gate and smoke test pass.

## Completion Criteria

- [ ] The design's lethal-source attribution, source-life guard, compact/detailed telemetry, SQLite durability, adaptive batch delivery, and Game Service idempotency are implemented.
- [ ] Python lint/tests, Java tests/build, migration tests, and real-server smoke pass.
- [ ] No Premium artifact, credential, or API assumption enters the repository or release artifact.
- [ ] The task is reviewed, committed, pushed, and the user receives the final file/commit summary.
