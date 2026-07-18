# Kill objective progress model

Date: 2026-07-18

## Question

How should a typed MythicMob kill objective derive durable progress while
preserving quest-acceptance timing, delayed Adapter outbox delivery, combat
idempotency, and future objective types?

## Comparable conventions and patterns

### Active-objective counters (BetonQuest-style)

BetonQuest models `mobkill` as an active objective with a target set, positive
required amount, and the player-facing properties `amount`, `left`, and
`total`. Progress belongs to the active objective rather than the player's
lifetime statistics. This matches normal quest expectations and supports
repeatable quests, but it requires durable per-objective state and an event
hook that advances only active objectives.

Reference:
`https://betonquest.org/2.2/Documentation/Scripting/Building-Blocks/Objectives-List/#entity-kill-mobkill`

### Derived state predicates (current `first-steps` pattern)

The existing `current_life_spirit_root_present` objective is a state predicate:
it is projected directly from authoritative current-life facts and does not
need a counter. This remains the right model for facts whose present value is
the objective. It should become one typed evaluator, not be forced into an
event-counter table.

### Aggregate-baseline counters

At acceptance, freeze the current `life_mob_kill_counters.kill_count`; project
quest progress as `current_total - accepted_baseline`.

Advantages:

* no additional write per quest objective on each kill;
* existing combat-event deduplication protects the aggregate;
* inexpensive projection.

Problems in this repository:

* Paper can retain a kill in the SQLite outbox while Game Service is down;
* a kill that occurred before acceptance can be delivered after acceptance;
* the delayed old kill increments the aggregate after the baseline and is then
  incorrectly counted for the quest;
* a baseline map is still required for every target in every objective.

This model is unsuitable when event occurrence time, not delivery order,
defines eligibility.

### Ledger queries since acceptance

Count `combat_kill_events` for the current life, target `internal_name`, and
`occurred_at >= quest_progress.accepted_at` whenever quest state is projected.

Advantages:

* exact occurrence-time semantics despite delayed delivery;
* no additional objective-progress write model;
* combat event deduplication already guarantees one row per source event.

Costs:

* repeated count queries scan/index the immutable event ledger;
* multiple objectives multiply query work;
* the current indexes separate `(life_id, occurred_at)` and
  `(mob_internal_name, occurred_at)` instead of the full quest lookup shape;
* future event retention would change quest correctness unless completed
  progress is frozen elsewhere.

This is acceptable for a prototype but does not establish the requested
multi-type objective foundation.

### Persisted event-objective progress (recommended)

Create durable progress rows keyed by current life, quest, and objective. The
quest definition declares whether an objective is:

* `state`: projected from current authoritative facts; or
* `event_counter`: initialized on acceptance and advanced from idempotent
  domain facts.

For a MythicMob kill fact, advance matching active objectives only when:

* the combat event was newly inserted, not replayed;
* its authoritative recipient life matches the quest life;
* its exact `internal_name` is in the objective target set;
* its `occurred_at` is not earlier than the quest's `accepted_at`;
* the objective has not reached its required count.

The combat fact, aggregate kill counter, and objective increment should commit
atomically through an application-level coordinator. Combat code must not
write quest tables directly; it emits a typed internal fact to a quest-progress
port implemented by the Quest module.

Advantages:

* correct under delayed outbox delivery and retries;
* stable completed progress even if combat-event retention is added later;
* natural support for future craft, collect, dialogue, area, and other event
  objectives without treating all objectives as lifetime predicates;
* cheap quest projection and clear `current / required` presentation.

Costs:

* additive schema and repository contracts;
* cross-module orchestration must preserve the existing lock order;
* quest revision/cache invalidation must advance when objective progress does.

## Repository mapping

* `quest_progress` already freezes quest definition version, status, and
  acceptance time but has no per-objective rows.
* `combat_kill_events` stores event identity, life, exact MythicMob name, and
  occurrence time.
* `life_mob_kill_counters` remains useful lifetime analytics; it should not be
  overloaded as active quest state.
* `QuestObjectiveProjection` already exposes `current`, `required`, and
  `completed`, so the Paper wire shape needs little or no expansion.
* Existing quest frozen-response idempotency remains the turn-in boundary;
  combat event identity becomes the progress-increment idempotency boundary.

## Recommendation

Use a typed evaluator registry plus persisted event-objective progress. Keep
the current spirit-root objective as a derived state evaluator and implement
MythicMob kills as the first event-counter evaluator. Count only kills whose
authoritative occurrence time is at or after acceptance unless the product
owner explicitly chooses lifetime/pre-acceptance credit.
