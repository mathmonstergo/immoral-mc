# Typed Quest Objectives Design

## Status

Approved for implementation on `feat/cultivation-progression`.

This slice extends the existing authoritative quest loop without adding sects
or replacing Minecraft advancements. The four supported gameplay objective
types are:

1. `item_delivery`
2. `mythicmob_kill_count`
3. `technique_layer_reached`
4. `realm_level_reached`

The existing `current_life_spirit_root_present` objective remains supported for
the `first-steps` quest.

## Objective Contract

Every objective has a stable `objective_id` unique within its quest and a
localized display label. A quest contains between one and twelve objectives,
matching the tracked sidebar's bounded presentation contract. Definitions are
typed and validated at catalog load; the Adapter never submits objective
values.

| Type | Configuration | Authoritative source | Completion |
| --- | --- | --- | --- |
| `item_delivery` | `item_code`, `required_quantity > 0` | current-life item balance | `quantity >= required_quantity` |
| `mythicmob_kill_count` | exact `mob_internal_name`, `required_count > 0` | inserted combat kill facts | persisted count `>= required_count` |
| `technique_layer_reached` | exact `technique_id`, `target_layer` in `1..13` | active current-life technique | derived/persisted current layer `>= target_layer` |
| `realm_level_reached` | numeric `target_level` in the realm catalog | current-life cultivation state | `current_level >= target_level` |

The wire projection remains deliberately generic:

```json
{
  "objective_id": "deliver-foundation-pills",
  "title": "交付筑基丹",
  "current": 2,
  "required": 5,
  "completed": false
}
```

For a technique objective, `current` is the current layer and `required` is
the target layer. For a realm objective, they are the current and target
numeric realm levels. Item and kill objectives use quantity/count directly.
No new objective-specific fields are required by Paper.

## State and Event Semantics

State objectives are evaluated from the current life at every projection and
at turn-in. A player who already has the required item balance, active
technique layer, or realm when accepting receives credit immediately. If a
technique is abandoned or a realm/technique state regresses before turn-in,
the predicate becomes false again.

Kill objectives are different: acceptance creates a durable zero-valued row
for each active event objective. A newly inserted, authoritative combat fact
advances all matching active objectives when:

* the combat fact belongs to the quest's current life;
* its exact `mob_internal_name` matches the configured target;
* `occurred_at >= accepted_at`;
* the source event was inserted for the first time; and
* the objective has not reached its required count.

Rewardable combat facts also carry the `source_life_id` observed by the
Adapter. A missing or stale source life is recorded as terminal
`current_life_unavailable`; the service never silently binds an unscoped
delayed event to whichever life is current when it is delivered.

The combat event, lifetime mob counter, cultivation reward, and quest-counter
increments commit in one Unit of Work. A replayed event returns the stored
combat result before any quest increment. A delayed pre-acceptance event is
therefore never converted into quest credit, while the same historical fact
can remain available to a later achievement system.

Multiple active quests may receive the same matching kill. Completed or
unavailable quests never receive progress.

## Persistence

Add `quest_objective_progress` with the composite key
`(life_id, quest_id, objective_id)` and these fields:

```text
life_id
quest_id
objective_id
definition_version
objective_type
target_id
required_value
current_value
updated_at
```

Only event-counter objectives have rows. The row is initialized to zero when
the parent `quest_progress` row is accepted. The repository increments it with
a bounded update (`min(current_value + 1, required_count)`) under the same
transaction that inserts the combat fact. State objectives do not duplicate
item, technique, or realm state in quest tables.

`quest_progress` remains the lifecycle source of truth (`active` or
`completed`), and `life_quest_states.revision` advances for acceptance,
completion, and event-counter changes. The interaction response also exposes
`revision.objectives`, a monotonic state-objective dependency revision built
from the cultivation-state revision and relevant item-stack revisions. Paper
uses all revision-vector components to prevent an older asynchronous refresh
from overwriting a newer item, technique, or realm projection. Existing frozen
operation responses remain the idempotency boundary for accept and turn-in.

## Item Delivery Turn-in

Projection reads item balances without consuming them. A turn-in first locks
all distinct required item stacks in lexicographic `item_code` order, verifies
every required quantity and replay identity, and only then calls the item
repository's batch-consumption boundary to debit the full aggregate. Each
debit uses the turn-in operation ID and audit type `quest_delivery`. Completion
and any future reward write share the same transaction. If a later item has a
cross-domain operation-ID conflict, the preflight rejects the batch before any
earlier item is changed.

If any stack is short, the service raises `quest.not_ready` before a debit.
No partial debit is committed. Replaying a successful operation returns its
frozen response and does not consume again. Duplicate item objectives for the
same `item_code` are rejected at catalog validation, avoiding ambiguous audit
aggregation and operation replay.

The current repository accepts stable item-code strings but has no complete
item definition catalog. Until that catalog exists, item IDs are validated as
non-empty bounded identifiers and authoritative balances remain the source of
truth.

## Cultivation Layer Invariant

`LifeTechnique.invested_amount` is the auditable canonical balance. The
`current_layer` column is a materialized projection used for cheap reads and
cross-module objectives. It must be updated in the same transaction whenever
investment changes, including:

* ordinary seclusion investment;
* technique mutation/transfer;
* abandonment or other debit/penalty paths; and
* breakthrough penalty allocation.

All paths use the one shared cultivation-domain `layer_for_investment` curve.
The repository validates the resulting balance and writes both
`invested_amount` and `current_layer` together. Cultivation service snapshots
and quest evaluation both read the synchronized persisted value; neither
implements a second compensating curve or a legacy fallback.

Before direct reads are enabled, migration `20260718_003` recalculates every
existing technique row with a frozen copy of the authored cultivation-domain
curve. Invalid legacy capacity or realm data fails the migration visibly
instead of leaving an untrusted layer projection in service; later curve
balance changes cannot rewrite this historical backfill.

The computation is a fixed twelve-transition loop, so deriving a value in a
read is `O(1)` with respect to player progress. Persisting the projection is
still required because it prevents stale denormalized data, makes objective
queries cheap, and gives one invariant for APIs, tasks, and future indexes.

## Game Service Flow

```text
Paper fact/action
  -> Game Service service
  -> one Unit of Work
     -> authoritative module repositories
     -> Quest objective evaluator
     -> quest projection / lifecycle mutation
  -> frozen response or typed error
```

`QuestService` loads a typed objective context for the current life. The
combat service calls an explicit quest progression port after a newly inserted
kill event, passing only authoritative event identity, life, mob ID, and
occurrence time. It does not submit a trusted count.

Application assembly resolves one `QuestDefinitionCatalog` and injects it into
both `QuestService` and `CombatRewardService`; custom catalogs must never be
wired into only one side of the progression path.

Quest projection uses AND semantics across all objectives. State is:

```text
available -> active -> ready_to_turn_in -> completed
```

The existing API paths and contract version remain unchanged. Empty
`provider_ids` continues to return the global tracked quest for asynchronous
Paper refreshes.

## Paper Refresh and Presentation

`QuestObjectiveSnapshot` already carries the required generic fields. The
scoreboard renderer changes from one hard-coded objective row to one stable row
per tracked objective, preserving title, `current / required`, and the next
action hint.

A coalescing tracked-quest refresher calls the existing interaction-state API
with `provider_ids: []` after:

* accepted or duplicate combat-kill results;
* successful item adjustments;
* seclusion settlement or technique mutation results; and
* realm/breakthrough results.

HTTP and JSON parsing remain off the Paper main thread. Publishing, cache
generation checks, scoreboard updates, and Bukkit APIs run on the main thread.
The refresher verifies account/life identity and drops stale responses.

## Validation and Error Rules

* Unknown objective type or missing type-specific field: catalog load failure.
* Non-positive quantities/counts/layers/levels: catalog load failure.
* Unknown MythicMob ID when a combat catalog is available: catalog load
  failure.
* Unknown technique ID: catalog load failure.
* Realm target outside the loaded realm catalog: catalog load failure.
* Item shortage at turn-in: `quest.not_ready`, zero item consumption.
* Missing current life or authoritative state: fail closed; never infer
  progress from Paper payloads.
* Idempotency key reused for a different quest operation: existing
  `quest.idempotency_conflict`.

## Verification Matrix

Backend tests cover:

* typed definition validation and catalog revision stability;
* each objective below, equal to, and above target;
* pre-acceptance kill exclusion, delayed outbox delivery, duplicate events,
  wrong mob/life, and multiple matching active quests;
* current-life isolation after reincarnation;
* item shortage rollback, successful atomic multi-item delivery, and replay;
* specified active technique versus another/abandoned technique;
* current layer persistence after investment and debit paths;
* mixed-objective AND projection, restart persistence, and turn-in idempotency.

Paper tests cover typed JSON compatibility, multi-row scoreboard rendering,
main-thread dispatch, coalesced refreshes, stale-life response rejection, and
refresh triggers for combat, items, and cultivation.
