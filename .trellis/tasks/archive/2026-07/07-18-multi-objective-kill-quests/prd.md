# brainstorm: typed multi-objective quests

## Goal

Upgrade the quest domain from its single spirit-root-presence objective into an
extensible typed-objective system that fully supports item delivery,
MythicMobs kill counts, specified-technique layer targets, and specified-realm
targets. Sect membership and the future replacement of vanilla advancements
are deliberately deferred.

## What I already know

* The user requires all four objective types in this slice: deliver a specified
  item and quantity, kill a specified number of MythicMobs, raise a specified
  technique to a specified layer, and reach a specified realm.
* A realm objective targets a configured realm; it is not merely "advance one
  realm from the value at acceptance."
* A technique objective targets a configured technique ID and layer; it is not
  merely "advance the currently active technique once."
* Sect membership is deferred.
* Replacing Minecraft's vanilla advancement content with this game's own
  advancement tree is a separate future task, not part of this slice.
* The current quest catalog has one objective type:
  `current_life_spirit_root_present`.
* `quest_progress` persists accepted/completed status and timestamps but has no
  generic per-objective counter storage.
* Combat ingestion already persists idempotent MythicMob kill facts and a
  compact per-life/per-`internal_name` aggregate in `life_mob_kill_counters`.
* Quest and combat repositories already share the Game Service unit of work;
  Paper must not submit trusted kill counts.
* Paper already supports Citizens quest providers, one tracked quest, dialogue
  state, accept, and turn-in presentation.
* The implementation must establish a reusable typed objective boundary rather
  than hard-code one quest, mob, item, technique, or realm into orchestration.

## Requirements

* Add an extensible typed quest-objective model with direct validation.
* Add an item-delivery objective keyed by an authoritative item ID and a
  positive required quantity.
* Add a MythicMob kill-count objective keyed by exact `internal_name` and a
  positive required count.
* Kill objectives count only authoritative kills whose occurrence time is at
  or after quest acceptance. Lifetime kills from before acceptance never count
  toward quest progress and are reserved for the later advancement/achievement
  reward system.
* Add a technique-layer objective keyed by an exact technique ID and a
  positive target layer. It completes when that specified technique's current
  layer is greater than or equal to the configured layer.
* Add a realm objective keyed by a configured target realm/level. It completes
  when the current life's authoritative realm/level is greater than or equal
  to the configured target.
* Support multiple heterogeneous objectives in one quest using AND semantics.
* Kill targets use the exact MythicMobs `internal_name` from the authoritative
  combat catalog. One accepted kill may advance every active matching quest,
  but never advances completed, unavailable, wrong-life, or non-matching
  objectives.
* Game Service startup validates MythicMob, technique/layer, realm, and
  bidirectional quest-provider references against the shared authoritative
  catalogs. Invalid content fails before serving players.
* Game Service derives progress from authoritative current-life combat facts;
  Adapter/client payloads never submit trusted progress numbers.
* A rewardable combat fact must carry the Adapter-observed `source_life_id`.
  Missing or stale life identity is terminal `current_life_unavailable` and
  never binds a delayed event to the life current at delivery time.
* Game Service derives item, technique, and realm state from authoritative
  current-life records; Adapter/client payloads never submit trusted balances,
  layers, or realms.
* Item availability is projected without consuming it. Turn-in consumes all
  required delivery items and completes/rewards the quest in one atomic
  transaction; insufficient items leave the quest active and consume nothing.
* Technique and realm objectives use current authoritative state and therefore
  recognize progress obtained before quest acceptance. They remain satisfied
  only while the current state still meets the target.
* Only an active instance of the configured technique satisfies a technique
  objective. An abandoned technique does not count.
* Cultivation mutations must maintain `life_techniques.current_layer` in the
  same transaction as `invested_amount`. The persisted layer is a materialized
  projection of the shared cultivation-domain curve and must update on both
  investment gains and losses; Quest does not duplicate a compensating layer
  calculation.
* Replayed combat events and quest operations cannot advance or reward twice.
* Accept/turn-in and kill progression serialize through the per-life quest
  revision so a concurrent accept cannot lose a committed kill.
* Concurrent item-operation UUID collisions return stable replay/conflict
  outcomes without leaking database uniqueness errors or partial consumption.
* Reincarnation isolates objective progress to the new current life.
* Existing `first-steps` behavior and frozen idempotent quest responses remain
  compatible with the new objective evaluator shape.
* Paper presents authoritative current/required objective progress and updates
  the tracked quest after relevant kills, item mutations, seclusion, technique
  mutations, and realm changes without blocking the main thread.
* Paper invalidates late login and tracked-quest completions across quit/kick,
  disable, and same-life reconnects with non-reusable attempt tokens.
* Public usage documentation is maintained under `docs/wiki/`. The quest page
  documents all objective types, authoring examples, Citizens binding,
  semantics, validation, verification, and current limitations. Public Wiki
  prose is written in Simplified Chinese while technical literals remain
  unchanged.

## Acceptance Criteria

* [x] Existing spirit-root objective tests remain green through the generalized
      objective evaluator.
* [x] An accepted item-delivery objective projects the authoritative held
      quantity up to its requirement, consumes the exact required quantity only
      at successful turn-in, and never partially consumes on failure.
* [x] An accepted MythicMob kill quest advances from authoritative kill facts.
* [x] Duplicate delivery of one kill event advances the quest at most once.
* [x] A kill racing with quest acceptance waits for acceptance and is counted
      exactly once when its occurrence is at or after `accepted_at`.
* [x] A kill occurring before quest acceptance does not advance the quest even
      when its outbox event is delivered after acceptance.
* [x] Wrong mob IDs, unattributed deaths, and kills for another life do not
      advance the objective.
* [x] A specified-technique objective remains incomplete when another
      technique advances and completes when the configured technique reaches or
      exceeds its configured layer.
* [x] A realm objective remains incomplete below its configured target and
      completes when the current life reaches or exceeds that target.
* [x] Existing qualifying technique layers and realm levels count immediately
      after acceptance.
* [x] An abandoned configured technique does not satisfy a technique objective;
      a later layer or realm regression is reflected before turn-in.
* [x] Every cultivation investment/debit path persists `current_layer` equal to
      the layer derived from the resulting authoritative investment.
* [x] A quest containing heterogeneous objectives becomes ready to turn in
      only when every objective is satisfied.
* [x] Concurrent cross-life/cross-domain item UUID collisions return a stable
      conflict and leave all loser stacks and audit rows unchanged.
* [x] Required progress survives Game Service and Paper restarts.
* [x] Reaching the target count projects `ready_to_turn_in`; turn-in remains
      idempotent.
* [x] Paper renders authoritative `current / required` progress for all four
      objective types through the existing tracked-quest UI.
* [x] Invalid provider relationships and unknown mob/technique/realm targets
      fail during application composition.
* [x] Quit/rejoin ABA and late login completions cannot overwrite the active
      player's task projection.
* [x] A discoverable Wiki covers every currently usable feature module and
      includes a durable documentation-update contract for future changes.
* [ ] Real Citizens-driven smoke flows complete the configured objective
      examples end to end.

The final Citizens smoke item remains pending until a follow-up content task
adds concrete production quests for these objective types. This slice keeps
the runtime catalog's existing `first-steps` content unchanged, while the
typed catalogs and PostgreSQL end-to-end fixtures exercise all four types.

## Technical Approach

Use typed, discriminated objective definitions with type-specific validation.
Spirit-root presence, item balance, active technique layer, and realm level are
state evaluators over current authoritative facts. MythicMob kills are event
counters persisted per life, quest, and objective.

Acceptance creates zero-valued rows only for event-counter objectives. A newly
inserted authoritative combat event advances all matching active rows only when
its occurrence time is at or after acceptance; duplicate delivery cannot
advance again. Quest projection combines persisted event values with current
state evaluations, and all configured objectives must pass before turn-in.

Turn-in locks delivery item stacks in stable item-code order, validates every
required balance and replay identity, consumes all quantities with one batch
boundary and `quest_delivery` audit entries, and completes the quest in the
same Unit of Work. No domain-failure response is committed after a partial
debit.

Paper keeps the current generic `current / required` wire projection, expands
the scoreboard to all objective rows, and uses one coalescing tracked-quest
refresh path after relevant authoritative mutations.

## Decision (ADR-lite)

**Context:** Kill progress depends on event occurrence after acceptance, while
item, technique, realm, and spirit-root completion depend on current state.
Delayed Paper outbox delivery makes a lifetime-counter baseline incorrect.

**Decision:** Combine persisted event-objective counters with current-state
evaluators. Keep the cultivation ledger/investment as the canonical source and
transactionally maintain `current_layer` as its queryable materialized
projection.

**Consequences:** The design adds one quest objective-progress table and a
combat-to-quest progression service boundary. It avoids historical-kill leaks,
keeps state regressions visible, supports mixed objectives, and makes technique
queries cheap and consistent. Cultivation tests must guard the new persisted
layer invariant.

## Definition of Done (team quality bar)

* Python unit/integration tests cover objective validation, progress semantics,
  idempotency, current-life isolation, and persistence.
* Java tests cover projection/parsing and non-blocking refresh behavior.
* Ruff, Python tests, Gradle tests, and Gradle build pass.
* Relevant quest/combat contracts and local smoke instructions are documented.
* Repository README files link to the public Wiki, and future public behavior
  changes are required to update the corresponding Wiki page in the same PR.
* Rollback can remove the new catalog entry without corrupting existing quest
  or combat history.

## Out of Scope (explicit)

* Sect membership or sect selection.
* Party-shared kills, assists, contribution thresholds, and highest-damage
  attribution.
* Vanilla mob objectives and client-submitted kill commands.
* Passive item collection, escort, location, crafting, timer, or dialogue-tree
  objectives in this first implementation.
* Multiple simultaneously tracked quests or a multi-quest selection UI.
* Live quest editing and database-authored quest definitions.
* New story text, quest rewards, provider NPC bindings, or balancing values for
  concrete production quests. This slice makes the four objective types fully
  usable and covers them with test catalogs without inventing game content.
* Replacing or repopulating Minecraft's vanilla advancement system; this will
  be designed as a separate later task.

## Technical Notes

* Existing catalog: `game-service/src/immortal_mmo/quest/definitions.py`.
* Existing objective enum: `game-service/src/immortal_mmo/quest/models.py`.
* Existing quest persistence: `game-service/src/immortal_mmo/quest/db_models.py`.
* Existing combat aggregates: `game-service/src/immortal_mmo/combat/db_models.py`.
* Existing authoritative item balances and item-adjustment services will be
  reused for delivery validation and atomic consumption.
* Existing cultivation current-life state and `life_techniques` will be reused
  for realm and specified-technique predicates. The current layer persistence
  defect is corrected at the cultivation mutation boundary first.
* Existing cross-domain transaction boundary:
  `game-service/src/immortal_mmo/core/uow.py`.
* Existing Paper quest flow lives under
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/quest/`.

## Research References

* [`research/kill-objective-progress-model.md`](research/kill-objective-progress-model.md)
  — recommends persisted event-objective progress for post-acceptance kills and
  authoritative state evaluators for realm and technique targets.
