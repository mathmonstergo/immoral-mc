# brainstorm: MythicMobs kill cultivation rewards

## Goal

Connect MythicMobs monster deaths to the authoritative Game Service so an
eligible player kill credits the current life's **unrefined cultivation**.
Combat rewards remain stored reserve only; they do not advance the realm bar
until a later seclusion flow consumes and refines that reserve.

## What I already know

* MythicMobs should own mob spawning, AI, mechanics, and presentation.
* The Paper Adapter may report a trusted server-side death fact, but it must not
  decide the final cultivation reward or directly mutate progression.
* The Game Service is authoritative for player identity, current life,
  cultivation state, reward calculation, deduplication, and persistence.
* The approved PostgreSQL design already reserves
  `life_cultivation_states` and append-only `cultivation_resource_entries`.
* Reward ingestion needs a stable source event ID so Paper retries or duplicate
  death delivery cannot credit cultivation twice.
* The current Adapter has no MythicMobs dependency or integration layer;
  `plugin.yml` only soft-depends on Citizens.
* The current Game Service has empty `combat` and `cultivation` packages, so
  this is a new cross-layer vertical slice rather than a small listener edit.

## Approved product decisions

* The first slice rewards only MythicMobs mobs explicitly present in a
  version-controlled Game Service reward catalog.
* The Adapter reports stable Mythic mob type ID, a unique kill/source event ID,
  killer Minecraft UUID, server/world facts, and optional presentation facts;
  it never submits a trusted cultivation amount.
* Deaths without a player killer are ignored by the first reward outbox. They
  are not useful for player cultivation/counts and avoiding them keeps ambient
  despawns/environmental deaths off the hot path. A future world-analytics
  stream may choose a separate policy.
* Ordinary vanilla mob kills are out of scope for the first slice.
* Reward values and level-scaling formulas are intentionally simple initially
  and can be rebalanced without changing the event ledger schema.
* Normal monster telemetry is compact: one immutable kill fact is retained for
  idempotency/audit and a per-life/per-mob counter is maintained for product
  queries. The Adapter does not persist verbose Bukkit objects, inventories,
  damage histories, or coordinates by default.
* Special/boss entries may opt into a larger detail snapshot through the
  Game Service reward/telemetry catalog; this is a server-side policy and is
  not a trusted amount or arbitrary field supplied by MythicMobs YAML.

## Open Questions

There are no remaining architecture-blocking questions for the first slice.
The initial policy credits the owner of the lethal attributable damage source.
The attribution boundary still permits highest-damage and multi-recipient Boss
policies later without relying only on `MythicMobDeathEvent#getKiller()`.

The outbox reliability decision is fixed in
[`research/adapter-outbox.md`](research/adapter-outbox.md): one bounded SQLite
writer with WAL and `synchronous=FULL`; the death listener waits only for the
short local commit, while all network delivery is asynchronous.

## Requirements (evolving)

* Listen to the supported MythicMobs death API/event, not generic entity naming
  or lore heuristics.
* The first version credits only the final killer reported by the supported
  server-side attribution policy. `MythicMobDeathEvent#getKiller()` is an
  integration input/fallback, not the sole source of truth for technique
  damage.
* Player techniques, projectiles, damage-over-time effects, summons, traps, and
  other delayed damage must preserve an explicit owning player UUID and
  optional technique/cast ID from application through every damage tick. A
  lethal delayed tick credits its owning player even if no Player entity is the
  direct damager at death.
* The Adapter maintains a bounded per-mob combat-attribution projection from
  final uncancelled damage. Future ImmortalMC technique implementations must use
  the shared attribution/damage gateway instead of applying anonymous damage.
* The first attribution policy credits the owner of the lethal attributable
  damage. A lethal damage-over-time tick, projectile, summon, trap, or formation
  credits the player/life captured by its combat source. Highest-damage and
  contribution-threshold policies are deferred.
* Preserve future party/contribution sharing by making reward deduplication
  unique per `(source event, recipient life)` rather than assuming one source
  event can have only one recipient forever.
* Fail visibly when the configured MythicMobs integration is incompatible; do
  not silently downgrade to vanilla entity detection.
* Resolve the player account/current life in Game Service by Minecraft UUID.
* Calculate the authoritative unrefined-cultivation reward from Game
  Service-owned content and rules.
* Maintain a version-controlled Game Service mob reward catalog keyed by the
  exact MythicMobs `internal_name`. Each entry selects a base integer reward and
  an optional shared versioned level-scaling curve; reward amounts are never
  read from MythicMobs YAML or accepted from the Adapter.
* Catalog loading fails fast on duplicate IDs, invalid integer values, unknown
  curve IDs, invalid level bounds, or arithmetic overflow risk.
* Unknown Mythic mob IDs have an explicit stable `not_rewardable` outcome and
  receive no implicit default reward.
* Atomically deduplicate the kill event, append the reward ledger entry, and
  increment the current life's unrefined cultivation balance.
* Replaying the same kill event returns the original result without a second
  credit.
* A kill event for a dead/reincarnated or missing current life must not credit a
  historical life.
* Game Service unavailability must not cause the Adapter to grant a local
  fallback reward.
* The first slice includes a durable Adapter outbox for pending kill facts.
  Game Service success or an idempotent replay acknowledgement removes the
  entry; retryable failures and Paper restarts preserve it for redelivery.
* The outbox stores only immutable server-side kill facts and delivery state. It
  is not an authoritative cultivation balance or alternate progression store.
* Implement the Adapter outbox with an embedded SQLite database in WAL mode.
  Use transactional inserts/acknowledgements, bounded retry metadata, and
  crash-safe replay instead of inventing an append-log database format.
* Apply SQLite `journal_mode=WAL`, `synchronous=FULL`, foreign keys, and a
  bounded busy timeout on every connection. A kill fact is considered captured
  only after its insert transaction commits; an in-memory-only enqueue is not a
  success.
* Serialize SQLite writes through one bounded writer executor. The Paper main
  thread may wait for the short local commit, but must never perform HTTP,
  DNS, Game Service response handling, or retry backoff work.
* Claim delivery rows with an expiring lease so a Paper restart recovers
  `in_flight` rows. Retry only transport/timeout/408/429/5xx failures with
  capped backoff; explicit domain outcomes and malformed/unrecoverable rows
  are terminal and must be acknowledged or dead-lettered visibly.
* Separate durable capture latency from remote delivery latency. The SQLite
  append remains immediate, while a configurable asynchronous delivery worker
  sends due rows in bounded HTTP batches.
* Delivery cadence is adjustable and load-aware. Under high Paper or Game
  Service load it may increase the interval and batch more rows, while a maximum
  pending-age guard prevents indefinite delay. Use an in-process scheduled
  executor rather than an operating-system cron job so plugin lifecycle,
  leases, per-event acknowledgements, and sub-minute scheduling remain local.
* The official free-distribution MythicMobs 5.12.1 API/runtime is the supported
  baseline for this slice and the CI/test-server target.
* Future Premium-only mechanics are optional follow-up integrations and must not
  leak unlicensed Premium binaries or assumptions into the free baseline.
* Premium binaries and credentials must not be committed, redistributed, or
  embedded in the ImmortalMC plugin artifact. Compilation and tests use the
  official free 5.12.1 MythicCraft Maven/API artifact.
* Persist a separate append-only `combat_kill_events` fact before/alongside
  reward processing. A cultivation reward entry references the kill fact; the
  reward ledger is not the source of truth for kill history.
* Keep ordinary kill facts small and indexed for event-id deduplication; expose
  `life_mob_kill_counters` (or an equivalent materialized aggregate) so count
  queries do not scan the event ledger. Do not add permanent verbose payloads
  for every ordinary mob kill in the first slice.
* The canonical configuration link is the exact MythicMobs `internal_name`.
  ImmortalMC's version-controlled Game Service catalog maps that name to
  reward and telemetry policy. Arbitrary custom YAML fields, runtime variables,
  or `~onDeath` mechanics are not required for the authoritative path.
* When free-version integration becomes difficult, research official
  MythicMobs Premium documentation/API before building an overlapping custom
  mechanism. Premium may be proposed as an additive, separately licensed
  upgrade when it materially reduces complexity, but it must not bypass Game
  Service authority or silently become a required dependency.

## Research References

* [`research/mythicmobs-api.md`](research/mythicmobs-api.md) — the official API
  provides `MythicMobDeathEvent`, `MythicMob#getInternalName()`, mob level,
  entity UUID, and killer; use the pinned `Mythic-Dist:5.12.1` compile-only
  dependency and a MythicMobs soft-dependency boundary.
* [`research/mythicmobs-editions.md`](research/mythicmobs-editions.md) — the
  current official free build is free-to-download but Modrinth marks it
  All Rights Reserved; the kill event API exists in both free 5.12.1 and the
  locally deployed Premium 5.13.0 snapshot.
* [`research/adapter-outbox.md`](research/adapter-outbox.md) — SQLite is a
  temporary per-node delivery queue, not a second gameplay database; it uses
  WAL, full synchronous commits, leases, and bounded retries while PostgreSQL
  remains authoritative.

## Feasible approaches

### A. Typed `MythicMobDeathEvent` integration (recommended)

Listen to the official death event, snapshot its typed facts, and send them to
Game Service asynchronously. This uses the API MythicMobs already provides and
avoids duplicate mob-identification logic.

### B. Bukkit death plus Mythic manager lookup

Listen to generic `EntityDeathEvent`, then ask `MythicBukkit` whether the entity
is a MythicMob. The official API supports this lookup, but it adds an unnecessary
second identification step when the typed death event already exists.

### C. Custom Mythic `~onDeath` mechanic

Require every rewardable mob definition to invoke an ImmortalMC mechanic. This
is configuration-heavy and makes missed configuration silently lose rewards,
so it is rejected for the universal progression pipeline.

## Decision (ADR-lite)

**Context**: MythicMobs already exposes a typed death event and official
compile-only API artifact.

**Decision**: Use `MythicMobDeathEvent` directly through a dedicated optional
integration package. Credit the owner of the lethal attributable damage source
in the first version; use `getKiller()` only as a compatible fallback. The
Adapter submits facts, never a trusted reward amount. Official free-distribution
MythicMobs 5.12.1 is the supported baseline; Premium-only work is deferred and
must be separately licensed and scoped if introduced later. Persist a generic
Combat kill fact first; derive the Cultivation reward from the Game Service mob
reward catalog and link it to that fact.

**Consequences**: MythicMobs remains optional for unrelated ImmortalMC features,
and the first combat-reward implementation remains portable to the official
free distribution. The integration avoids duplicated mob detection, and future
multi-recipient rewards remain possible through per-recipient ledger
deduplication. A durable local outbox preserves immutable kill facts across
temporary Game Service outages and Paper restarts without becoming a second
progression authority.

## Acceptance Criteria (evolving)

* [ ] One eligible MythicMob kill credits the correct current life exactly once.
* [ ] Repeated delivery of the same source event ID does not change the balance.
* [ ] Unknown/unrewardable Mythic mob types produce no credit with an explicit
      stable outcome.
* [ ] Catalog validation and deterministic reward calculation have direct unit
      tests, including mob-level boundaries and overflow limits.
* [ ] The Adapter cannot inject an arbitrary cultivation amount.
* [ ] Restart preserves unrefined cultivation and the append-only reward event.
* [ ] A kill captured while Game Service is unavailable is delivered exactly
      once after recovery, including across a Paper restart.
* [ ] Every accepted MythicMob death produces at most one durable combat kill
      fact per source event and recipient-independent source identity.
* [ ] SQLite outbox recovery handles duplicate enqueue, retryable HTTP failure,
      successful acknowledgement, malformed/corrupt rows, and bounded retry
      scheduling without blocking the Paper main thread for network work.
* [ ] Batch delivery returns and applies an independent terminal/retry result
      for each event; an ambiguous batch timeout is safe to replay.
* [ ] Configured high-load delivery cadence reduces HTTP pressure without
      weakening immediate SQLite capture or exceeding the maximum pending age.
* [ ] Lethal direct, projectile, damage-over-time, summon, trap, and formation
      sources credit their owning player/life; Mythic's killer is a compatible
      fallback rather than the only attribution source.
* [ ] Reincarnation isolates later kills to the new life.
* [ ] Java tests cover MythicMobs present/absent/incompatible and event mapping.
* [ ] Python unit/integration tests cover reward calculation, transactionality,
      idempotency, current-life locking, and restart persistence.

## Definition of Done (team quality bar)

* Design and implementation plan are approved before coding.
* PostgreSQL migration, repository/service/API, and Paper Adapter integration
  are implemented as one tested vertical slice.
* Python lint/tests and Java Gradle test/build are green.
* A local server smoke proves a real MythicMob kill credits reserve exactly
  once and survives Game Service restart.
* Relevant Trellis backend conventions are updated if the integration creates a
  reusable event-ingestion pattern.

## Out of Scope (explicit)

* Seclusion/offline refinement and realized realm progression.
* Final cultivation balance numbers or time-to-realm tuning.
* Authoritative Game Service combat damage calculation.
* Party sharing and contribution calculation, anti-boosting, daily caps, rested bonus,
  loot, quest kill objectives, and vanilla mob rewards until explicitly chosen.
* MythicMobs directly writing PostgreSQL or calling cultivation mutation logic.

## Technical Notes

* MythicMobs is not yet declared in
  `minecraft-nodes/main-plugin/build.gradle.kts` or `plugin.yml`.
* Adapter composition is currently centralized in
  `ImmortalMainPlugin.onEnable()` and has an optional-integration pattern for
  Citizens that may inform, but not dictate, the MythicMobs boundary.
* Approved data flow:
  `MythicMobs death fact -> ImmortalMC Adapter -> Game Service calculation ->
  cultivation ledger/balance -> Adapter presentation/logging`.
* Schema reference:
  `docs/superpowers/specs/2026-07-14-minecraft-postgresql-schema-design.md`
  sections 7–9.
