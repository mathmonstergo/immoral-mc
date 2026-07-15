# Cultivation level XP feedback

## Goal

Give players immediate, physical feedback after an authoritative MythicMob
reward by spawning owner-bound experience orbs at the death location and
projecting cultivation state through a two-bar bottom HUD. The main bar shows
realized progress toward the next realm and replaces the vanilla numeric level
with a Chinese realm name; a thinner gray bar directly below it shows stored
unrefined cultivation. Define the initial progression ladder from 练气一层
through 元婴后期; 元婴后期 is the current maximum and all 化神 levels are
excluded. Add an extensible major-realm breakthrough model, with the first
complete rule set covering the special 练气十至十三层 -> 筑基初期 path.

## What I already know

* Game Service is authoritative for combat rewards and currently credits
  `unrefined_cultivation` atomically after an accepted kill.
* The current combat response already returns `event_id`, `life_id`,
  `reward_amount`, and `unrefined_balance` for accepted/duplicate events.
* The Adapter outbox currently acknowledges the response and discards its
  presentation fields; no player chat, XP orb, level, or progress-bar feedback
  exists.
* Vanilla experience orbs move toward nearby players and normally increase the
  vanilla XP bar when collected.
* Vanilla XP is also affected by enchanting, Mending, death loss, `/xp`, and
  unrelated mob XP, so it cannot be the authoritative cultivation store.
* A reward presentation must occur only after Game Service returns an
  authoritative `accepted` result. It must not be spawned optimistically at
  death, on `duplicate`, or for terminal no-reward outcomes.
* The existing cultivation design separates unrefined reserve from realized
  progression. The user confirmed this boundary remains mandatory: monster
  kills never directly advance the cultivation realm.
* The clientbound vanilla experience packet contains one progress float, one
  integer level, and one total-XP integer. Paper exposes one corresponding XP
  bar and cannot send a Chinese string in the integer level field or add a
  second vanilla XP bar.
* The exact requested presentation therefore requires a custom HUD delivered
  through a server resource pack (or a client mod). BetterHud supports a
  server-side HUD, auto-generated resource packs, text/images/animation,
  Bukkit/Paper 1.21+, and a Bukkit API.
* The user chose mob-level-scaled orb count as visual feedback only. The number
  of spawned orbs has no relationship to the authoritative cultivation reward
  amount credited by Game Service.
* Authoritative reward state changes immediately after Game Service accepts a
  kill. Paper delays only the visible HUD-growth animation until the visual
  orbs reach the owning player; reconnect synchronizes the final state.
* The requested numeric-to-name ladder is:
  1–13 练气一层 through 练气十三层; 14–16 筑基初/中/后期; 17–19
  结丹初/中/后期; 20–22 元婴初/中/后期.
* Cross-major-realm XP requirements use approved escalating multipliers:
  练气十三层突破筑基 ×3, 筑基后期突破结丹 ×4, and 结丹后期突破元婴
  ×5. Within-realm growth is ×1.5 for 练气, ×1.7 for 筑基, ×1.8 for
  结丹, and ×2 for 元婴, flooring each calculated value to an integer.
* Potion attribution is explicitly deferred and is not part of this task.
* Existing immutable spirit-root state already distinguishes `penta`, `quad`,
  `triple`, `dual`, `variant`, and `celestial`; root count is available from
  its canonical base elements (variant and celestial are single-root cases).
* No authoritative item inventory/consumption system is implemented yet, so
  筑基丹 requires a minimal item ownership and atomic-consumption slice or a
  separately scoped prerequisite.
* Existing architecture notes reserve persisted cultivation sessions and
  integer basis-point probabilities for future seclusion/breakthrough rules.
* The existing combat-reward module provides a suitable precedent: committed
  JSON content, typed immutable definitions, strict startup validation, and
  Game Service-owned resolution.

## Assumptions (temporary)

* Experience orbs are a presentation mechanism, not trusted currency.
* Orbs should be owner-bound so another player cannot steal cultivation
  feedback or cause the wrong HUD to update.
* Player login/reconnect must resynchronize the cultivation HUD from Game
  Service even if the player was offline when an outbox reward was delivered.
* 元婴后期 is a hard cap. On reaching it, the primary bar displays full, the
  unrefined reserve capacity becomes zero, and no hidden 化神 progress exists.
* Maximum unrefined storage is one full level's XP requirement for the
  player's current realm level. Once full, later rewards do not increase the
  reserve. Because level requirements increase monotonically, refining a full
  reserve can cross at most one level boundary.
* The primary HUD bar represents realized progress within the current realm;
  the thinner gray lower bar represents unrefined reserve capacity.
* Players must accept the server-delivered resource pack. No separately
  installed client mod is required.
* The first implemented major-breakthrough rule is 练气 -> 筑基. Later
  筑基 -> 结丹 and 结丹 -> 元婴 rules use the same rule interface but are not
  assigned invented item/chance conditions in this task.

## Open Questions

* What exact pill-count-to-success probability curves should apply to four-
  and five-root players below the guaranteed ten-pill attempt?

## Requirements (evolving)

* Spawn XP-orb feedback only for authoritative accepted MythicMob rewards.
* Scale the visual number of reward orbs from the MythicMob level. Orb count
  must not calculate, encode, or constrain the credited cultivation amount.
* Preserve Game Service authority and idempotency; Paper must not calculate or
  persist trusted cultivation progression.
* Monster kills add only unrefined cultivation reserve. Realm XP and realm
  level change only when a later seclusion/refinement operation converts that
  reserve.
* Commit the authoritative cultivation credit immediately on an accepted
  reward. When the owner is online, animate the gray reserve bar toward the
  committed value as the visual orbs arrive; otherwise show the committed
  value on the next authoritative HUD synchronization.
* Cap unrefined reserve at the current numeric level's full XP requirement.
  The cap does not expand based on partial realized progress.
* When a reward would exceed the cap, credit only the amount that fills the
  remaining capacity and discard the excess; do not reject the whole reward
  and do not queue overflow for later.
* Once the reserve is full, later kills do not add unrefined cultivation until
  seclusion consumes reserve and creates capacity again.
* A normal refinement seclusion that consumes the entire stored reserve may
  advance at most one adjacent numeric level. A configured major-realm
  breakthrough is a distinct transition and may skip optional numeric stages.
* Present two independently controlled bottom-HUD progress bars: the normal
  main bar for realized progress toward the next numeric realm, and a thinner
  gray bar immediately below it for unrefined reserve fill.
* Replace the player-visible vanilla numeric level presentation with the full
  Chinese realm name. Use internal numeric realm IDs only in authoritative
  state, APIs, logs, and calculations.
* Treat both bars and the Chinese label as projections of Game Service state,
  never as authoritative XP storage.
* Use BetterHud as the server-side HUD renderer and require its automatically
  delivered resource pack for players joining this server. Do not require a
  separately installed client mod.
* BetterHud/resource-pack presentation failures must not roll back, duplicate,
  or otherwise change authoritative combat rewards.
* Support exactly 22 current levels, ending at 元婴后期.
* At level 22, report zero unrefined capacity and credit zero cultivation from
  further kills. Still spawn the mob-level-scaled visual orbs for an accepted
  kill, but never imply that those orbs contain authoritative XP.
* Render the level-22 primary bar as full and the thin gray reserve bar as
  empty/disabled.
* Use the version-controlled 1–22 realm catalog and integer thresholds defined
  in Technical Approach. Game Service owns this catalog; Paper consumes
  returned state instead of recalculating thresholds.
* Major-realm transitions never happen automatically when cultivation fills.
  Game Service evaluates a versioned breakthrough rule containing eligibility,
  item costs, success probability, duration, target level, and failure effects.
* Unlike later major realms, 练气 -> 筑基 becomes eligible beginning at
  练气十层. Eligible source levels are 10, 11, 12, and 13; a successful attempt
  transitions directly to level 14 筑基初期 and skips any remaining optional
  练气 layers.
* A 筑基 attempt may start only when the primary realized-progress bar for the
  player's current eligible 练气 layer is completely full.
* The 练气 -> 筑基 attempt requires 筑基丹 and a persisted breakthrough
  seclusion lasting 10–15 minutes. The exact duration-selection rule remains
  configurable rather than embedded in Paper.
* For one-, two-, and three-root players, one 筑基丹 is sufficient and a
  full 练气十层-or-higher attempt succeeds with 100% probability. If such a
  pill has been consumed when the player starts seclusion at full 练气十层,
  settlement automatically transitions to 筑基初期.
* Four- and five-root players may consume additional 筑基丹 to increase the
  success probability monotonically. At ten consumed pills, success is 100%;
  the lower-count probability curve is versioned Game Service configuration.
* On a failed four-/five-root attempt from full 练气十、十一、or 十二层,
  consume the completed layer progression and advance the player to the next
  练气 layer with zero realized progress in that new layer. They cannot retry
  until the new layer's primary progress bar is full.
* On a failed four-/five-root attempt from full 练气十三层, keep the player at
  full 练气十三层. Consumed pills remain spent, and another attempt may start
  after the player consumes the required pills again.
* Do not add a redundant general-purpose aptitude score to the life row. Derive
  root count from the immutable spirit-root facts and allow rule profiles to
  match root count and, later, explicit quality codes when needed.
* Store breakthrough balance in a committed, versioned, strictly validated
  Game Service JSON catalog modeled after the combat reward catalog. Do not
  scatter realm-specific probability tables through service `if/else` code.
* Persist a frozen decision snapshot on every breakthrough session, including
  rule identity/version, source and target levels, failure mode/target,
  spirit-root quality and derived count, consumed pills, success basis points,
  timing, status, and idempotency identity. Catalog changes must not alter an
  in-progress session.
* Item validation, pill consumption, seclusion creation, and the eventual
  deterministic/random breakthrough settlement are authoritative atomic or
  idempotent Game Service operations. Paper only requests and presents them.
* Keep potion attribution out of scope.

## Acceptance Criteria (evolving)

* [ ] An accepted kill produces visible owner-bound XP-orb feedback at the mob
      death location.
* [ ] Orb count visibly scales with MythicMob level while changing neither the
      credited reward amount nor reserve calculations.
* [ ] Game Service credit is committed before orb pickup, while the HUD growth
      animation follows owner pickup and reconnect snaps to committed state.
* [ ] Another player cannot receive or consume the reward presentation.
* [ ] Duplicate/replayed/no-reward events do not spawn a second reward display.
* [ ] The two-bar cultivation HUD resynchronizes from authoritative state after
      login/reconnect.
* [ ] The primary bar shows realized progress and the thin gray lower bar
      independently shows unrefined reserve fill.
* [ ] Players see the correct Chinese realm name in place of the vanilla
      numeric level for internal levels 1–22.
* [ ] A player accepting the required server resource pack sees the intended
      layout without installing a client mod.
* [ ] BetterHud being unavailable cannot corrupt or duplicate cultivation
      rewards; the adapter logs a clear presentation failure.
* [ ] Kills never directly change the authoritative realm level.
* [ ] Unrefined reserve never exceeds the current level's full XP requirement.
* [ ] A reward that crosses the storage cap credits only the remaining
      capacity and discards its excess without rejecting the accepted kill.
* [ ] Rewards received while storage is full do not increase the reserve.
* [ ] Normal refinement of a full reserve advances at most one adjacent level
      in one seclusion.
* [ ] Progress cannot advance past 元婴后期.
* [ ] At 元婴后期, accepted kills credit zero cultivation while retaining
      visual orb feedback; the main bar stays full and the reserve bar stays
      empty/disabled.
* [ ] A player at eligible 练气 levels 10–13 can start a 筑基 breakthrough and
      success transitions directly to level 14.
* [ ] Levels below 练气十层 cannot start the 筑基 breakthrough.
* [ ] An eligible 练气 player whose current primary progress bar is not full
      cannot start a 筑基 attempt.
* [ ] One-/two-/three-root players require exactly one 筑基丹 and receive a
      guaranteed eligible breakthrough when the cultivation-full condition is
      satisfied.
* [ ] Four-/five-root success probability increases with consumed pill count
      and equals 100% at ten pills.
* [ ] A failed four-/five-root attempt from levels 10–12 advances exactly one
      练气 layer, resets that new layer's realized progress to zero, and cannot
      be retried until the new layer is full.
* [ ] A failed level-13 attempt remains at full 练气十三层, consumes its pills,
      and can be safely retried without duplicating the prior settlement.
* [ ] Changing the breakthrough catalog after a session starts does not change
      that session's frozen success probability, timing, or failure behavior.
* [ ] A persisted 10–15 minute breakthrough survives retries and cannot double
      consume pills or settle twice.
* [ ] Tests cover accepted, duplicate, offline, reconnect, competing-player
      pickup, level-up, early 筑基 from levels 10–13, pill-count validation,
      breakthrough success/failure, retry, restart, and cap behavior.

## Definition of Done

* Game Service progression catalog/state/API, breakthrough session, and minimal
  筑基丹 ownership/consumption changes are typed and migrated.
* Adapter response/presentation flow and owner-bound orb handling are tested.
* Python Ruff/tests and Java Gradle tests/build pass.
* Local Paper smoke verifies kill -> authoritative reward -> visible orb -> HUD
  sync -> persisted reconnect state.
* Relevant Trellis specs are updated with the XP-as-presentation boundary.

## Decision (ADR-lite)

**Context**: The vanilla experience packet carries one progress float and an
integer level, so it cannot render a Chinese realm label and a second thin bar
in the requested position.

**Decision**: Integrate BetterHud and require its automatically delivered
server resource pack. Render realized progress, the Chinese realm name, and
the gray unrefined-reserve bar as a custom bottom HUD. Keep all displayed
values as projections of Game Service state.

**Consequences**: Players must accept the resource pack but do not install a
client mod. BetterHud becomes an optional-at-load, required-for-presentation
server dependency; gameplay rewards must remain safe if it is unavailable.

### Major-breakthrough rule model

**Context**: 练气 may break through from four different numeric levels and its
conditions depend on spirit-root count, item quantity, probability, and a
persisted duration. Later major realms will have different conditions.

**Decision**: Model major breakthroughs as versioned Game Service rules and
persisted sessions, separate from ordinary adjacent-level refinement. The
first rule targets 筑基初期 from any eligible 练气 level 10–13.

**Consequences**: The system supports future condition types without putting
realm-specific logic in Paper. This task must add the minimal authoritative
item-consumption boundary needed for 筑基丹, but does not invent later-realm
requirements.

### Aptitude facts versus balance rules

**Context**: Spirit-root quality/count is a player fact, while pill
requirements, probability curves, and failure transitions are game-balance
rules that will evolve and differ by major realm.

**Decision**: Keep `life_spirit_roots` as the source of aptitude facts; derive
root count rather than storing a redundant score. Put breakthrough balance in
a versioned JSON catalog interpreted by typed generic Game Service code. Freeze
the resolved decision in each persisted breakthrough session.

**Consequences**: Balance can change through reviewed catalog commits without
rewriting player birth facts or realm-specific service branches. PostgreSQL
retains enough frozen evidence for retries, audits, restarts, and historical
explanations.

## Technical Approach

Interpret each `max_exp` as the realized cultivation required to leave that
numeric level. Start level 1 at 100 and floor after every multiplication.
Level 22 is terminal and therefore has no authoritative `max_exp` or level 23;
its HUD is rendered as complete immediately on entry.

| Level | Player-visible realm | max_exp |
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
| 11 | 练气十一层 | 5,743 |
| 12 | 练气十二层 | 8,614 |
| 13 | 练气十三层 | 25,842 |
| 14 | 筑基初期 | 43,931 |
| 15 | 筑基中期 | 74,682 |
| 16 | 筑基后期 | 298,728 |
| 17 | 结丹初期 | 537,710 |
| 18 | 结丹中期 | 967,878 |
| 19 | 结丹后期 | 4,839,390 |
| 20 | 元婴初期 | 9,678,780 |
| 21 | 元婴中期 | 19,357,560 |
| 22 | 元婴后期 | — (terminal) |

Multiplier placement is deliberate: the `max_exp` on levels 13, 16, and 19
is the high-cost final-stage capacity. The 练气 -> 筑基 breakthrough is an
explicit exception: it may target level 14 from levels 10–13 instead of
requiring level 13.

## Out of Scope (explicit)

* Potion/damage-over-time attribution fixes.
* 化神期 and any realm above 元婴后期.
* Letting vanilla enchanting, Mending, commands, or unrelated XP mutate
  authoritative cultivation.
* General techniques, cultivation zones, offline refinement rates, pill poison,
  heart demons, and seclusion gameplay beyond the required 筑基 breakthrough
  session.
* Concrete 筑基 -> 结丹 and 结丹 -> 元婴 breakthrough conditions.
* Party reward sharing, loot, and vanilla mob rewards.

## Technical Notes

* Relevant Game Service files:
  `cultivation/db_models.py`, `combat/service.py`, `combat/schemas.py`, player
  login/current-life projections, a new version-controlled realm catalog,
  breakthrough rules/sessions, and minimal authoritative item consumption.
* Relevant Adapter files:
  `OutboxDeliveryWorker`, combat batch DTOs, `ImmortalMainPlugin`, player login
  lifecycle, and new XP-orb/HUD presentation listeners.
* Current data flow ends at:
  `accepted response -> outbox acknowledge`; presentation must consume the
  per-event result without weakening acknowledgement/retry behavior.
* Recommended breakthrough persistence separates immutable/configured facts:
  spirit root remains in `life_spirit_roots`; rule definitions live in a
  committed catalog; sessions and item/resource ledger rows store authoritative
  attempt snapshots and mutations.

## Research References

* [`research/minecraft-dual-cultivation-hud.md`](research/minecraft-dual-cultivation-hud.md)
  — vanilla exposes one numeric XP channel; an exact two-bar Chinese realm HUD
  needs a server resource pack, with BetterHud as the recommended renderer.
* [`research/versioned-breakthrough-rules.md`](research/versioned-breakthrough-rules.md)
  — derive aptitude from immutable spirit-root facts, keep balance in a typed
  versioned catalog, and freeze each attempt decision in PostgreSQL.
