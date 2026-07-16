# Cultivation Progression, Techniques, Seclusion, and Breakthrough Design

**Date:** 2026-07-16  
**Status:** Approved  
**Task:** `.trellis/tasks/07-15-cultivation-level-xp-feedback`

## 1. Purpose and Scope

This design turns cultivation rewards into a complete authoritative progression
loop:

```text
MythicMob reward
  -> unrefined reserve
  -> area-bound seclusion
  -> retained technique investment
  -> current-realm progress
  -> adjacent advancement or configured major breakthrough
```

It also adds owner-bound XP-orb feedback and a BetterHud projection containing
a Chinese realm label, a current-realm progress bar, and a thinner gray
unrefined-reserve bar.

This release implements only the common generated-curve technique model. It
stores and validates typed effect definitions and projects their layer-scaled
values, but it does not execute attacks, control, buffs, healing, casting,
targeting, cooldowns, or other live combat behavior. Authored cross-realm
techniques, 青元剑诀 continuation-volume fusion, forced-training backlash, and
parent-derived branch techniques are future work.

## 2. Authority and Component Boundaries

Game Service and PostgreSQL own all trusted cultivation state and decisions:

```text
Paper / BetterHud
  - capture player intent and presentation facts
  - show orb/HUD/GUI feedback
  - never calculate trusted XP, probabilities, rates, or realm transitions

Game Service
  - validate content, selections, areas, items, and spirit-root compatibility
  - settle rewards, seclusion, technique investment, realm records, and breakthroughs
  - return immutable presentation projections

PostgreSQL
  - authoritative ledgers, balances, sessions, entry records, and frozen decisions
```

Visual XP orbs are owner-bound feedback. They appear only after an authoritative
`accepted` MythicMob result. They do not contain cultivation currency and do
not mutate vanilla XP.

## 3. Realm Catalog

The catalog contains player-visible levels 1 through 22. `max_exp` is the
current-realm-local cultivation needed to fill that level, not a lifetime-total
threshold.

| Level | Realm | max_exp |
| ---: | --- | ---: |
| 1 | 练气一层 | 100 |
| 2 | 练气二层 | 150 |
| 3 | 练气三层 | 225 |
| 4 | 练气四层 | 337 |
| 5 | 练气五层 | 505 |
| 6 | 练气六层 | 757 |
| 7 | 练气七层 | 1,135 |
| 8 | 练气八层 | 1,702 |
| 9 | 练气九层 | 2,553 |
| 10 | 练气十层 | 3,829 |
| 11 | 练气十一层 | 5,169 |
| 12 | 练气十二层 | 6,978 |
| 13 | 练气十三层 | 9,420 |
| 14 | 筑基初期 | 43,931 |
| 15 | 筑基中期 | 74,682 |
| 16 | 筑基后期 | 298,728 |
| 17 | 结丹初期 | 537,710 |
| 18 | 结丹中期 | 967,878 |
| 19 | 结丹后期 | 4,839,390 |
| 20 | 元婴初期 | 9,678,780 |
| 21 | 元婴中期 | 19,357,560 |
| 22 | 元婴后期 | 116,145,360 |

Levels 10 through 13 use iterative `floor(previous * 1.35)`, replacing the old
level-13 spike. Their cumulative qi investment floors are
`11,293 / 16,462 / 23,440 / 32,860`.

Level 14 remains the approved independent 筑基初期 anchor. Levels 16, 19, and
22 preserve the cross-major floor pattern ×4, ×5, and ×6. Level 22's value is
the hypothetical cultivation floor for future 化神初期. It is fillable, but no
level 23 or 化神 breakthrough exists in this release.

## 4. Cultivation Balances and Progress

Each life has three distinct projections:

1. `unrefined_cultivation`: reserve credited by rewards and consumed only by
   ordinary seclusion.
2. `realized_cultivation_total`: a transactionally maintained aggregate equal
   to all retained active technique investment.
3. `current_realm_progress`: investment in the current realm's backing group
   above the baseline recorded on entry to that realm.

The main HUD bar uses `current_realm_progress / current_level.max_exp`. It never
uses lifetime realized cultivation. The gray HUD bar uses unrefined reserve and
the current credit cap.

An upward transition preserves all technique investment, lifetime realized
cultivation, and unrefined reserve. The target realm records a new baseline, so
the main bar changes from full to empty. Training an earlier retained group
afterward increases lifetime cultivation but cannot advance the current bar.

## 5. Realm-Entry Records and Regression

Every successful numeric transition appends an ordered realm-entry record with:

- source and target level IDs;
- source backing-group ID and the frozen investment floor that justified entry;
- target backing-group ID and its investment baseline at entry;
- transition kind and breakthrough-session ID when applicable;
- content/rule versions and timestamps.

For ordinary exact-level groups, the target baseline is normally zero. Optional
练气 levels 11 through 13 reuse the shared `qi` group, so their target baseline
is the unchanged qi investment at the moment of advancement.

After any technique debit, abandonment, replacement, or partial transfer, Game
Service validates realm-entry records oldest to newest. It keeps the longest
prefix whose source-group floors are still satisfied, invalidates every higher
record, and rebuilds local progress from the last valid target baseline. This
permits minor- and major-realm regression without negative progress. A later
return to an invalidated major realm requires a new breakthrough and a new
entry record.

## 6. Unrefined Reserve Rules

Only two operations mutate the reserve:

- an authoritative accepted reward increases it;
- ordinary seclusion consumes it.

Breakthrough success/failure, realm advancement/regression, and technique
abandonment/transfer never clear or consume reserve.

The normal reward-credit cap is the current level's `max_exp`. A reward credits
only remaining capacity and discards overflow. If realm loss lowers the cap
below an existing balance, the balance is preserved, new rewards credit zero,
and seclusion remains available. Positive-cap fill clamps at 100%; a positive
balance with a zero cap would also render full, although all current catalog
levels now have positive caps.

At 元婴后期, rewards continue filling the `116,145,360` reserve cap and
seclusion may fill level-22 techniques. Filling the main bar leaves the player
at level 22.

## 7. Common Technique Model

Technique definitions are committed, versioned, and strictly validated. A
definition contains:

- stable ID and localized metadata;
- canonical required elements and minimum realm;
- group: shared `qi` or exact player level 14 through 22;
- major realm and time weight;
- maximum layer 13;
- typed prerequisites and equipped-item requirements;
- typed layer-aware effect data for validation/projection only.

Compatibility requires an intersection between required canonical elements and
the life's spirit-root elements. An empty requirement is universal. Display
strings never drive compatibility.

The shared qi group retains up to nine techniques. Every later exact-level
group retains up to five. Three mastered techniques are the normal sufficient
baseline; extra techniques provide progression capacity and redundancy.

One mastered qi technique retains `3,765`. The three/five/seven/nine pattern
can therefore back qi levels 10/11/12/13. One mastered non-qi technique retains
`ceil(level.max_exp / 3)`.

## 8. Technique Layer Curves

Each group has twelve positive integer transition costs from layer 1 to layer
13. Growth ratios are:

- qi: 1.5;
- 筑基 groups: 1.7;
- 结丹 groups: 1.8;
- 元婴 groups: 2.0.

For ratio `p/q`, transition `i` uses exact weight
`p^i * q^(11-i)`. Game Service calculates floor quotas against the sum of
weights, then assigns leftover points by descending fractional remainder, with
lower transition index as the deterministic tie-breaker. The twelve costs must
sum exactly to the technique's mastered capacity on every platform.

## 9. Ordinary Seclusion

Paper presents an inventory GUI listing authoritative learned techniques and
allows one to five selections. All selected techniques must currently train in
the same major realm. Game Service revalidates learned state, compatibility,
realm/prerequisites, capacity, area, and definition versions.

A session freezes:

- selected technique IDs and versions;
- area ID/version;
- speed and yield basis points;
- resolved major-realm time values;
- idempotency identity and timing.

There is no technique ordering. Effective cultivation is divided equally among
non-full selections. When one fills, unused share is repeatedly redistributed
among remaining techniques. Stable technique ID breaks integer remainders, so
GUI click order cannot affect settlement.

Reserve consumption is capacity-aware. Yield may exceed 1×, but reserve that
cannot fit is not consumed. Reserve debit, technique-ledger credits, realized
aggregate update, and realm recalculation commit atomically. When all selected
techniques fill, the session ends automatically and unused reserve remains.

## 10. Time and Areas

The baseline clock is one game year per real-world hour. Ordinary full mastery
uses 10% of the major realm's maximum lifespan:

| Major realm | Weight | Neutral full mastery |
| --- | ---: | ---: |
| 练气 | 1 | 10 hours |
| 筑基 | 2 | 20 hours |
| 结丹 | 5 | 50 hours |
| 元婴 | 10 | 100 hours |

Areas carry independent integer basis-point modifiers:

- `speed_basis_points`: game years advanced per real hour;
- `yield_basis_points`: technique investment retained per reserve consumed.

Area identity, version, and both modifiers freeze at session start.

## 11. Major Breakthroughs

Major transitions are versioned Game Service rules and persisted sessions.
Every attempt requires authoritative current-realm-local progress equal to the
source level's `max_exp`. The HUD is only a projection.

The first complete rule is 练气 levels 10–13 to 筑基初期:

- one/two/three roots: exactly one 筑基丹, 100%;
- four roots, pills 1–10: `5/10/16/24/32/42/53/67/82/100%`;
- five roots, pills 1–10: `2/4/7/11/16/22/29/36/43/50%`.

The catalog stores explicit basis-point lookup tables. Generic orchestration
selects a typed profile; it does not branch on localized root qualities.

On a failed four/five-root attempt from qi levels 10–12, a frozen secondary
50/50 roll either:

- advances one optional qi level, preserving all balances/investment and
  recording the unchanged qi investment as the new entry baseline; or
- applies the fixed technique-backed penalty.

At qi level 13, failure always applies the penalty. Later major-realm failures
also always apply it.

The penalty is `floor(source_level.max_exp / 3)`. Qi uses all nonzero
techniques in the shared qi group; later realms use all nonzero techniques in
the exact source-level group. The fixed total is independent of technique
count and is randomly partitioned with a versioned symmetric strategy. Frozen
entropy, participating IDs, final debits, rolls, catalog versions, consumed
items, and timing make settlement replay-safe and auditable.

## 12. Presentation

BetterHud/resource-pack presentation shows:

- full Chinese realm name;
- current-realm-local main progress;
- thin gray unrefined reserve progress.

Entering every new level, including 元婴后期, shows an empty main bar. Filling
元婴后期 shows full but never advances beyond level 22. Reconnect always
resynchronizes from Game Service.

Presentation failures never roll back or duplicate authoritative mutations.

## 13. Failure Handling and Idempotency

All reward, seclusion, transfer, realm-recalculation, item-consumption, and
breakthrough mutations are atomic or idempotent. Active sessions freeze their
content decisions, so catalog reloads do not change historical settlement.

Random breakthrough and penalty-allocation results are resolved once and
persisted. Retries and restarts reuse the stored result and cannot consume
items/reserve twice or apply duplicate technique debits.

## 14. Verification

Automated tests cover:

- realm table and layer-curve exact sums;
- nine/five group capacity and selection limits;
- reward cap/overflow, over-cap-on-regression, and reserve mutation boundaries;
- equal seclusion allocation, redistribution, yield, and time modifiers;
- technique-ledger/realized-total invariants;
- group-scoped progress and realm-entry rollback;
- all pill probability tables and validation;
- 50/50 optional qi advancement and fixed-loss outcomes;
- frozen replay/idempotency and cross-major regression;
- HUD projections, reconnect, and owner-bound reward-orb behavior.

Paper smoke verifies the authoritative reward-to-orb/HUD path and seclusion GUI
projection. Full technique combat execution is not part of the smoke or this
release.

