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
* The earlier 练气十三层 ×3 XP spike is superseded by the requirement to make
  练气十至十三层 smooth and reachable within nine ordinary qi techniques.
  筑基后期突破结丹 ×4 and 结丹后期突破元婴 ×5 remain approved. Ordinary
  within-realm growth uses ×1.5 for 练气 technique layers, ×1.7 for 筑基,
  ×1.8 for 结丹, and ×2 for 元婴, flooring each calculated value to an integer.
* Potion attribution is explicitly deferred and is not part of this task.
* Existing immutable spirit-root state already distinguishes `penta`, `quad`,
  `triple`, `dual`, `variant`, and `celestial`; root count is available from
  its canonical base elements (variant and celestial are single-root cases).
* No authoritative item inventory/consumption system is implemented yet, so
  筑基丹 requires a minimal item ownership and atomic-consumption slice or a
  separately scoped prerequisite.
* Existing architecture notes reserve persisted cultivation sessions and
  integer basis-point probabilities for future seclusion/breakthrough rules.
* The user requires ordinary realization of unrefined cultivation to happen
  through seclusion in eligible world areas. Different areas may apply
  independently configured speed and yield multipliers.
* Ordinary seclusion requires at least one equipped cultivation technique.
  For each seclusion the player selects one to five concrete techniques through
  an in-game GUI. There is no persistent or per-session technique ordering. A
  selected technique stops accepting cultivation once it reaches maximum layer
  13.
* The broader technique system has not yet been designed. The existing schema
  design only reserves `life_techniques` and a selected technique on persisted
  cultivation sessions; it does not define multi-selection, per-layer
  thresholds, or the relationship between technique progress and realm XP.
* The user clarified that realized cultivation and technique investment are the
  same retained cultivation, not two independent progress tracks. A seclusion
  increases player cultivation only by the amount successfully stored in the
  selected techniques. Abandoning/replacing a technique removes the cultivation
  invested in it, except for any amount explicitly preserved and transferred,
  and the player's realm may fall when the backed total decreases.
* The current implementation scope contains only the ordinary/common technique
  progression model. Techniques with authored cross-realm progression, such as
  the discussed 青元剑诀 design, are a future separate model and must not distort
  the common model's schema or balance formulas in this task.
* 练气 techniques are the deliberate exception: all 练气 techniques belong to
  one shared `qi` technique group and do not distinguish player numeric levels
  1–13. Its target is the cumulative cultivation required to fill 练气十层:
  11,293. Each mastered 练气 technique retains 3,765 cultivation, so three
  mastered techniques retain 11,295.
* The global five-technique-slot model from Mortals is discarded. The player
  may retain up to nine techniques in the shared `qi` group and up to five
  ordinary techniques in every later exact numeric realm-level group
  (筑基初期, 筑基中期, etc.). Earlier groups remain retained when the player
  advances. Three mastered techniques are only the sufficient 练气十层
  baseline; additional techniques provide optional progression capacity and
  redundancy against later abandonment/transfer loss.
* Technique definitions carry a major-realm cultivation-time field.
  The canonical time-weight ratio is 练气:筑基:结丹:元婴 = 1:2:5:10, matching
  the corresponding maximum-lifespan anchors 100:200:500:1000. A single
  seclusion may select techniques from only one major realm.
* The baseline clock is one in-game year per real-world hour. Mastering one
  technique from layer 1 to 13 at a neutral area takes 10% of its major realm's
  maximum lifespan: 10/20/50/100 real hours for 练气/筑基/结丹/元婴 before
  area or other modifiers.
* The legacy `/home/adam/projects/mortals` project confirms the intended model:
  hard required-element intersection with spirit-root elements, universal
  techniques with no required element, minimum-realm/tier gates, layers 1–13,
  configured per-layer effect growth, up to five technique slots, optional
  transfer items that preserve a percentage of old technique cultivation,
  and realm loss when discarded investment crosses a realm threshold.
* The existing combat-reward module provides a suitable precedent: committed
  JSON content, typed immutable definitions, strict startup validation, and
  Game Service-owned resolution.
* Four-root and five-root breakthrough balance is intentionally asymmetric:
  four-root players can reach a guaranteed attempt at the pill cap, while
  five-root players use a steeper curve whose maximum success probability is
  only 50%.
* Breakthrough-loss penalties are fixed by the attempted source level, not by
  how many techniques the player retained. Because an attempt requires the
  source level to be cultivation-full, the aggregate penalty is one third of
  that source level's configured `max_exp`; the fixed total is then randomly
  distributed across the invested techniques in the relevant backing group.
  A player with nine techniques therefore loses the same aggregate cultivation
  as a player with three techniques.
* When the 50% failure outcome advances a player from 练气十至十二层 to the
  next optional 练气 layer, all existing realized cultivation and qi-technique
  investment remain unchanged. Advancement never consumes or resets the
  completed source-layer cultivation.
* The future 青元剑诀-style model may use authored layer costs, realm caps,
  fusion unlocks, and slot-exempt inherited branches, but none of those fields,
  fixtures, services, or GUI flows are implemented by this task.
* The approved smooth 练气十至十三层 `max_exp` values are
  `3,829 / 5,169 / 6,978 / 9,420`, generated by iterative ×1.35 with flooring.
  Their cumulative cultivation totals are
  `11,293 / 16,462 / 23,440 / 32,860`, which fit the shared qi group's
  three/five/seven/nine-technique progression pattern.

## Assumptions

* The project is still zero-to-one. No production cultivation data or schema
  history must survive this work. The final persistence shape is written into
  the clean development schema baseline, and local PostgreSQL volumes are reset
  and recreated. Do not implement legacy columns, data backfills, dual
  reads/writes, compatibility adapters, or downgrade/re-upgrade support for the
  obsolete development schema.
* Experience orbs are a presentation mechanism, not trusted currency.
* Orbs should be owner-bound so another player cannot steal cultivation
  feedback or cause the wrong HUD to update.
* Player login/reconnect must resynchronize the cultivation HUD from Game
  Service even if the player was offline when an outbox reward was delivered.
* 元婴后期 is the current realm cap but still has a fillable local-progress
  requirement representing the cultivation floor for a future 化神初期
  breakthrough. Entering 元婴后期 shows an empty main bar; filling it does not
  create level 23 or hidden 化神 progression.
* One full level's XP requirement is the normal unrefined reward-credit cap for
  the player's current realm. Realm loss may preserve an existing balance above
  the new cap; such a balance blocks further credits rather than being destroyed.
* The primary HUD bar represents realized progress within the current realm;
  the thinner gray lower bar represents unrefined reserve capacity.
* Players must accept the server-delivered resource pack. No separately
  installed client mod is required.
* The first implemented major-breakthrough rule is 练气 -> 筑基. Later
  筑基 -> 结丹 and 结丹 -> 元婴 rules use the same rule interface but are not
  assigned invented item/chance conditions in this task.

## Requirements

* Spawn XP-orb feedback only for authoritative accepted MythicMob rewards.
* Scale the visual number of reward orbs from the MythicMob level. Orb count
  must not calculate, encode, or constrain the credited cultivation amount.
* Preserve Game Service authority and idempotency; Paper must not calculate or
  persist trusted cultivation progression.
* Monster kills add only unrefined cultivation reserve. Realm XP and realm
  level never change directly from a kill. Ordinary growth comes from
  seclusion/refinement, while breakthrough settlement and technique loss may
  also change the numeric realm without consuming unrefined reserve.
* Commit the authoritative cultivation credit immediately on an accepted
  reward. When the owner is online, animate the gray reserve bar toward the
  committed value as the visual orbs arrive; otherwise show the committed
  value on the next authoritative HUD synchronization.
* Use the current numeric level's full XP requirement as the unrefined-credit
  cap. The cap does not expand based on partial realized progress.
* When a reward would exceed the cap, credit only the amount that fills the
  remaining capacity and discard the excess; do not reject the whole reward
  and do not queue overflow for later.
* Once the reserve is full, later kills do not add unrefined cultivation until
  seclusion consumes reserve and creates capacity again.
* Only authoritative accepted rewards may increase unrefined reserve, and only
  ordinary seclusion/refinement may consume it. Realm advancement,
  breakthrough success/failure, technique abandonment/transfer, and realm
  recalculation never clear, consume, or otherwise mutate the reserve.
* Because technique loss may lower the player into a realm with a smaller
  credit cap, an unchanged reserve may temporarily exceed that new cap. Preserve
  the balance rather than destroying it, render the reserve bar as full, and
  credit no further rewards until seclusion reduces the balance below the cap.
  Over-cap reserve does not prevent seclusion or limit how much otherwise-valid
  reserve that seclusion may consume. For a positive cap, HUD fill is
  `min(balance / cap, 1)`; for cap zero, any positive carried balance renders
  full until consumed.
* Ordinary refinement may occur only through a persisted seclusion started in
  an eligible cultivation area and with at least one compatible equipped
  technique. A configured major-realm breakthrough remains a distinct
  transition and may skip optional numeric stages.
* Model cultivation areas as stable semantic IDs with versioned, fixed-point
  speed and yield modifiers owned by Game Service. Paper reports the resolved
  area ID and presents the session; it does not calculate authoritative rates.
* Represent area modifiers in integer basis points. `speed_basis_points`
  changes the game-year clock (`10000` = one game year per real hour;
  `20000` = two game years per real hour). `yield_basis_points` changes
  effective retained cultivation per reserve consumed (`10000` = 1:1;
  `15000` allows 100 reserve to produce 150 effective cultivation before
  capacity clamping).
* Freeze the area identity, content version, speed, and yield values when a
  seclusion starts. Moving away, reloading content, or editing an area must not
  retroactively change an active session.
* Apply fixed-point arithmetic and floor only at the documented settlement
  boundary. Limit reserve consumption to the amount whose yield can actually
  fit in the selected techniques; area bonuses may create more retained
  cultivation than reserve consumed, but capacity overflow never consumes or
  destroys additional reserve.
* Provide a Paper inventory GUI that lists authoritative learned techniques with
  group, attribute, layer, progress, full/eligible state, and lets the player
  select one to five techniques for a seclusion. Game Service must revalidate
  the submitted selection; GUI state is never authoritative.
* The GUI may select one to five techniques only when all selections share the
  same major-realm code. Game Service rejects mixed-major-realm selections even
  if a stale or manipulated client GUI submits them.
* Persist the selected technique IDs and frozen definition versions when
  ordinary seclusion starts. Do not persist or infer an allocation order.
* Split each settlement's effective cultivation equally across all selected
  techniques that still have capacity. If a technique reaches layer 13 before
  using its share, repeatedly redistribute the unused amount equally across the
  remaining selected techniques. Assign indivisible integer remainders by
  stable technique ID so GUI click order never changes the result.
* If settlement fills a realm and that transition is deterministic, create the
  realm-entry record atomically. Continue with remaining effective cultivation
  only while the target level uses the same selected backing group and does not
  require an explicit major breakthrough. Shared-qi settlement may cross
  ordinary levels up to full 练气十层, but stops at the 筑基 barrier and at full
  optional 练气十一至十三层. Exact-level groups stop when their current level
  fills, leaving unused reserve intact for a later selection.
* When every selected technique is mastered or becomes mastered, automatically
  settle and end the seclusion. Consume only the unrefined cultivation that was
  successfully retained as technique investment; leave all unused reserve in
  authoritative storage.
* A seclusion settlement calculates one effective-cultivation amount from the
  consumed reserve and frozen area/session modifiers, then offers it to the
  selected-technique allocator. Credit realized player cultivation only for the
  amount actually retained by those techniques. Reserve consumption, technique
  investment, realized-total change, and realm recalculation commit in one
  authoritative transaction.
* Treat technique investment ledger entries as the auditable backing for
  realized cultivation. Maintain the player's realized total as a fast
  transactionally consistent aggregate/projection equal to retained active
  technique investment, with invariant tests preventing drift.
* Track current-realm progress separately from lifetime realized cultivation
  and scope it to the current realm's backing group. Investment added to an
  earlier retained group after advancement increases lifetime realized
  cultivation but never advances the current realm's main bar.
* Persist an ordered realm-entry record for every successful upward numeric
  transition. It freezes source/target levels, the source backing group and
  required investment floor that justified the transition, the target backing
  group, that target group's investment baseline at entry, a generation ID,
  parent active-entry ID, and active/invalidated status. Retain all existing
  technique investment and the realized-total aggregate. On first entry to a
  target group, current progress is investment gained above the entry baseline.
  On re-entry after regression, previously retained target-group investment is
  restored as current local progress instead of being hidden behind a new
  baseline; this is the deliberate exception to the empty-bar-on-entry rule.
* For the shared `qi` group, source and target group are both `qi` for optional
  练气十一至十三层 transitions. The 50% failed-breakthrough advance outcome
  records the unchanged qi investment as the target entry baseline, making the
  new main bar empty without deleting any technique investment.
* After any technique debit/removal, validate only the current parent-linked
  active realm-entry chain from oldest to newest. Keep the longest prefix whose
  frozen source-group investment floors remain satisfied; invalidate that
  branch's higher transitions and return the player to the target of the last
  valid entry (or the base realm). Rebuild local progress from retained
  target-group investment, clamp it to `0..max_exp`, and never reactivate an
  invalidated entry. Re-advancement appends a new generation/branch from the
  last valid active entry.
* Store technique definitions in committed, versioned, strictly validated
  content. Each definition has a stable ID, attribute codes, a technique group,
  maximum layer 13, and typed layer-aware gameplay effects. The group is either
  the special shared `qi` group or an exact numeric player realm level 14–22.
* Add a major-realm code and cultivation-time weight to every technique
  definition. Strictly validate the canonical weights qi=1, foundation=2,
  core=5, nascent_soul=10; freeze selected techniques' time values and
  definition versions in the seclusion decision snapshot.
* Use a base full-mastery duration equal to 10% of the
  canonical major-realm maximum lifespan. With the one-year-per-real-hour
  clock, neutral full-mastery durations are qi=10h, foundation=20h, core=50h,
  nascent_soul=100h. Partial progress and multi-selection derive duration
  proportionally from remaining capacity and equal allocation.
* Freeze the selected techniques' mastered capacities and full-mastery
  duration. For `n` selections with capacities `C_i`, cumulative time-limited
  effective cultivation after `elapsed_seconds` is
  `floor(elapsed_seconds * speed_basis_points * sum(C_i) /
  (full_mastery_seconds * n * 10000))`. Store the cumulative generated total so
  repeated settlement uses the difference from the prior cumulative floor.
* Let `effective_cap` be the smaller of unused cumulative time budget and
  selected-technique remaining capacity. The largest reserve amount convertible
  without exceeding it is
  `floor((((effective_cap + 1) * 10000) - 1) / yield_basis_points)`.
  Clamp this to available reserve, then retain
  `floor(reserve_consumed * yield_basis_points / 10000)`. Persist cumulative
  reserve-consumed and retained totals so repeated settlements preserve fixed
  point remainders and never over-consume.
* Allow at most nine retained ordinary techniques in the shared `qi` group and
  at most five retained ordinary techniques in every later exact-realm group.
  Do not use a global technique-slot limit; advancing to another exact realm
  group does not evict techniques retained in earlier groups.
* Ordinary seclusion may target any one to five learned, compatible,
  non-mastered techniques that the player explicitly selects and currently
  satisfies. Selection is not restricted to the player's current technique
  group. Earlier groups remain retained backing; abandoning an earlier
  technique can still recalculate the player downward when the remaining total
  crosses a realm threshold.
* Generate one shared 12-transition geometric layer curve per technique group.
  Use growth 1.5 for the shared `qi` group, 1.7 for levels 14–16, 1.8 for
  levels 17–19, and 2.0 for levels 20–22, matching the approved player
  cultivation family multipliers. Layer 13 is terminal.
* Normalize the twelve transition costs to the technique's exact mastered
  capacity with deterministic largest-remainder allocation. For growth ratio
  `p/q`, use exact integer weights `p^i * q^(11-i)` for transitions `i=0..11`,
  calculate each floor quota against the sum of weights, then assign leftover
  points by descending fractional remainder with lower transition index as the
  tie-breaker. The twelve integer costs must sum exactly to mastered capacity.
* For every non-qi exact-level group, set one mastered technique's retained
  cultivation capacity to `ceil(player_level.max_exp / 3)`. Three mastered
  techniques therefore back at least the level requirement and exceed it by no
  more than two cultivation points, providing the requested integer tolerance.
* For the shared `qi` group, use target 11,293 and mastered capacity 3,765 per
  technique. Three mastered 练气 techniques therefore retain 11,295, a tolerance
  of two cultivation above the full-练气十层 cumulative target.
* The elevated final-stage requirements on player levels 16 and 19 already
  include the approved cross-major multipliers ×4 and ×5. Technique curves use
  those larger `max_exp` totals as their target and must not multiply them a
  second time. Level 13 no longer receives a separate ×3 spike.
* Derive each technique's layer and within-layer progress from its
  total authoritative invested cultivation and the generated group curve.
  Curves are catalog-derived shared definitions, not duplicated per technique.
* Interpret technique effect definitions through a closed typed vocabulary and
  layer gates/scaling data. Do not add `if technique_id == ...` behavior to the
  cultivation or combat services. This task validates and projects configured
  effect values by layer but does not execute attacks, control, buffs, healing,
  targeting, casting, cooldowns, or other live combat effects.
* Follow the Mortals compatibility baseline: a non-universal technique may be
  learned/equipped only when at least one required canonical element matches
  the current life's spirit-root elements; an empty required-element list is
  universal. Variant/celestial compatibility uses explicit canonical codes,
  never localized display-string parsing.
* Enforce the technique's minimum realm when consuming/learning its technique
  item, equipping it, and starting seclusion. Support typed equipped-item and
  prerequisite-technique-layer requirements from versioned content.
* Support validated effect data that may unlock at specific layers and/or scale
  by layer. Keep acquisition, progression, and the future casting/targeting/
  effect executors as separate consumers of the same definition so later
  combat implementation does not require changing cultivation storage.
* Seed representative strict-schema test definitions adapted from Mortals:
  qi-group 引气术 (`GF_YinqiShu_01`), 冰冻术 (`Gongfa_68726c`), 缠绕术
  (`Gongfa_b8d7e3`), 地刺术 (`Gongfa_6fcf01`), 火弹术
  (`Gongfa_eff4d0`); level-14 燃血斩 (`GF_RanxueZhan_01`), 灵力针刺
  (`Gongfa_8c1470`), and 风裂遁刃诀 (`Gongfa_Fenglie_01`). Preserve their
  representative attributes/categories/effect shapes while adapting balance
  fields to ImmortalMC's group curves and authority model.
* Abandoning or replacing a technique must atomically remove its total invested
  cultivation. A configured transfer item may preserve a validated
  fraction and move only the amount that fits the target technique; the
  destroyed remainder reduces realized cultivation and triggers authoritative
  realm recalculation.
* Realm recalculation after technique loss may cross major-realm boundaries.
  There is no permanent floor from an earlier successful breakthrough. A player
  who falls from 筑基 back into 练气 must later satisfy the current eligibility,
  pill-consumption, seclusion, and success rules to break through again.
* Present two independently controlled bottom-HUD progress bars: the normal
  main bar for realized progress toward the next numeric realm, and a thinner
  gray bar immediately below it for unrefined reserve fill.
* Project the main bar from current-realm-local progress, not lifetime realized
  cultivation. After any successful transition to the next numeric realm, the
  main bar changes from full to empty while the historical technique ledger and
  lifetime realized-total aggregate remain intact, including entry into level
  22 元婴后期.
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
* Give level 22 a configured `max_exp` of `116,145,360`, calculated as the
  hypothetical 化神初期 floor by applying the next cross-major multiplier ×6
  to 元婴中期's `19,357,560`. This value controls the level-22 main bar,
  unrefined credit cap, and ordinary level-22 technique capacity only; no
  化神 realm or breakthrough is enabled.
* Continue accepting capped unrefined rewards at level 22 and allow ordinary
  seclusion to fill level-22 techniques and the main bar. Once the main bar is
  full, keep the player at level 22 and render it full; extra retained
  technique redundancy never creates hidden level-23 progress.
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
* A 筑基 attempt may start only when authoritative current-realm-local progress
  for the player's eligible 练气 layer equals that source level's configured
  `max_exp`. Apply the same cultivation-full eligibility condition to every
  later minor- or major-realm breakthrough. The full HUD bar is only a
  projection of the Game Service-owned group/checkpoint calculation.
* The 练气 -> 筑基 attempt requires 筑基丹 and a persisted breakthrough
  seclusion lasting 10–15 minutes. The exact duration-selection rule remains
  configurable rather than embedded in Paper.
* For one-, two-, and three-root players, one 筑基丹 is sufficient and a
  full 练气十层-or-higher attempt succeeds with 100% probability. If such a
  pill has been consumed when the player starts seclusion at full 练气十层,
  settlement automatically transitions to 筑基初期.
* Four-root players may consume 1–10 筑基丹. Their success probability follows
  the approved quasi-exponential table 5%, 10%, 16%, 24%, 32%, 42%, 53%, 67%,
  82%, and 100%, represented as 500, 1000, 1600, 2400, 3200, 4200, 5300,
  6700, 8200, and 10000 integer basis points in versioned Game Service
  configuration rather than calculated by Paper.
* Five-root players may consume 1–10 筑基丹. Their probability follows a
  separate, monotonically increasing quasi-exponential table: 2%, 4%, 7%, 11%,
  16%, 22%, 29%, 36%, 43%, and 50%, represented as 200, 400, 700, 1100, 1600,
  2200, 2900, 3600, 4300, and 5000 basis points. It is capped at 50% even at
  ten pills; five-root attempts have no guaranteed pill count.
* On a failed four-/five-root attempt from full 练气十、十一、or 十二层,
  resolve a separately frozen 50/50 secondary outcome. One outcome advances
  the player exactly one optional 练气 layer. The other applies a fixed
  technique-backed cultivation penalty equal to one third of the attempted
  source level's configured full `max_exp`.
* On a failed four-/five-root attempt from full 练气十三层, always apply the
  fixed technique-backed cultivation penalty; there is no further optional
  练气 layer to receive the 50% advance outcome.
* For failed breakthroughs in later major realms, always apply the same fixed
  penalty model: one third of the attempted source minor realm's configured
  full `max_exp`.
* Calculate the fixed aggregate penalty as
  `floor(source_level.max_exp / 3)`, independently of whether the player
  retained three through nine techniques. For 练气, the relevant backing group
  is the entire shared `qi` group; for later realms, it is the attempted source
  minor realm's exact-level group. Randomly partition that exact aggregate
  across every nonzero-investment technique in that group.
* Use a versioned, statistically symmetric random-partition strategy driven by
  frozen 256-bit breakthrough-session entropy. In allocation round `r`, derive
  each eligible technique's positive 64-bit weight from the first eight bytes
  of `HMAC-SHA256(entropy, r || technique_id)`, interpreted unsigned, plus one.
  Allocate proportionally with exact integer largest-remainder quotas, cap each
  debit by available investment, remove saturated techniques, and repeat with
  the next round for overflow. Break equal fractional remainders by the same
  round's full HMAC digest.
  No technique may be debited below zero; redistribute any unavailable share
  among the remaining techniques. Persist the resolved per-technique debits so
  retries reproduce the same result rather than rolling again.
* Apply the per-technique debits and reduce the realized player cultivation by
  exactly their aggregate in the same authoritative transaction. Recalculate
  realm state afterward, including any permitted minor- or major-realm loss.
  If the relevant entry records remain valid, current local progress falls by
  the debit total; otherwise unwind invalid entry records and rebuild progress
  under the lower realm. Never produce negative local progress. Consumed
  breakthrough items remain spent regardless of secondary outcome.
* Do not add a redundant general-purpose aptitude score to the life row. Derive
  root count from the immutable spirit-root facts and allow rule profiles to
  match root count and, later, explicit quality codes when needed.
* Store breakthrough balance in a committed, versioned, strictly validated
  Game Service JSON catalog modeled after the combat reward catalog. Do not
  scatter realm-specific probability tables through service `if/else` code.
* Represent each chosen quasi-exponential curve as an explicit validated
  pill-count-to-success-basis-points table in the committed catalog. Runtime
  settlement reads the selected profile's table and does not evaluate
  floating-point exponentials.
* Model aptitude-specific pill behavior through a small closed set of typed
  success models selected by a root-count profile. The initial models are a
  fixed guaranteed model for one-/two-/three-root players and independently
  configured pill-count lookup-table profiles for four- and five-root players.
  Generic orchestration asks
  the selected model to validate pill count and resolve basis points; it must
  not branch on individual root qualities or embed the awkward rule in nested
  service `if/else` statements.
* Keep profile selection, pill-count validation, probability resolution, item
  consumption, session creation, and settlement as separate responsibilities.
  Both success models return the same frozen decision shape before the atomic
  mutation begins.
* Persist a frozen decision snapshot on every breakthrough session, including
  rule identity/version, source and target levels, failure mode/target,
  spirit-root quality and derived count, consumed pills, success basis points,
  primary success roll, secondary failure-mode roll when applicable, resolved
  source-level `max_exp`, fixed penalty total, participating technique IDs,
  random-partition strategy/version and entropy, resolved per-technique debits,
  timing, status, and idempotency identity.
  Catalog changes must not alter an in-progress session.
* Allow at most one active cultivation mutation session per life. While a
  breakthrough is pending, reject ordinary seclusion, technique
  abandonment/replacement/transfer, and another breakthrough. Combat rewards
  may still add unrefined reserve because breakthrough settlement never consumes
  it. Release exclusivity only when the session settles or is cancelled under
  its frozen rule.
* Item validation, pill consumption, seclusion creation, and the eventual
  deterministic/random breakthrough settlement are authoritative atomic or
  idempotent Game Service operations. Paper only requests and presents them.
* Keep potion attribution out of scope.

## Acceptance Criteria

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
* [ ] The primary bar shows current-realm-local progress and the thin gray lower
      bar independently shows unrefined reserve fill; neither uses lifetime
      realized cultivation as its numerator.
* [ ] Players see the correct Chinese realm name in place of the vanilla
      numeric level for internal levels 1–22.
* [ ] A player accepting the required server resource pack sees the intended
      layout without installing a client mod.
* [ ] BetterHud being unavailable cannot corrupt or duplicate cultivation
      rewards; the adapter logs a clear presentation failure.
* [ ] Kills never directly change the authoritative realm level.
* [ ] Reward credit never raises unrefined reserve above the current level's
      cap. If realm loss makes an unchanged reserve exceed the smaller new cap,
      the balance is preserved, the bar renders full, and later rewards credit
      zero until seclusion consumes it below the cap.
* [ ] Over-cap reserve does not block seclusion. Positive-cap HUD fill clamps at
      100%; at zero cap, a positive carried balance renders full until consumed.
* [ ] A reward that crosses the storage cap credits only the remaining
      capacity and discards its excess without rejecting the accepted kill.
* [ ] Rewards received while storage is full do not increase the reserve.
* [ ] Breakthrough success/failure, upward or downward realm recalculation, and
      technique abandonment/transfer do not mutate unrefined reserve; accepted
      rewards add it and ordinary seclusion is the only operation that consumes
      it.
* [ ] Ordinary refinement cannot start outside an eligible cultivation area or
      without at least one compatible equipped technique.
* [ ] The in-game GUI allows selecting one to five eligible concrete techniques,
      and Game Service rejects stale, incompatible, mastered, or otherwise
      invalid selections authoritatively.
* [ ] The GUI and Game Service reject a multi-selection containing techniques
      from different major realms.
* [ ] Ordinary seclusion freezes the selected technique IDs/definition versions
      without creating an implicit order; a mastered technique accepts no more
      cultivation.
* [ ] Multi-selection divides cultivation equally, dynamically redistributes
      capacity overflow, and produces identical results regardless of GUI click
      order.
* [ ] Cumulative elapsed-time settlement uses the frozen capacity/time formula,
      repeated partial settlements equal one combined settlement, and the
      inverse yield bound never consumes reserve whose effective result cannot
      fit.
* [ ] Shared-qi settlement may create multiple deterministic ordinary-level
      entries in one transaction but stops at full 练气十层, full optional
      练气十一至十三层, or any explicit major barrier. Exact-level selection
      stops when its current level fills and leaves unused reserve intact.
* [ ] Seclusion ends automatically when all selected techniques are mastered,
      consumes only retained cultivation, and preserves unused unrefined
      reserve.
* [ ] Technique time weights validate as 1/2/5/10 for qi/foundation/core/
      nascent-soul content and are frozen for persisted seclusion settlement.
* [ ] At neutral speed, one game year equals one real-world hour and a full
      technique takes 10/20/50/100 hours by major realm before modifiers.
* [ ] Speed and yield modifiers are independent, frozen, basis-point values;
      tests cover neutral and accelerated/high-yield areas, capacity clamping,
      and yield greater than consumed reserve without reserve over-consumption.
* [ ] One settlement consumes reserve once and increases realized cultivation
      by exactly the amount retained in selected technique investment; the
      aggregate and technique ledger cannot diverge.
* [ ] Lifetime realized cultivation equals retained technique investment, while
      the primary HUD bar uses only current-realm-local progress.
* [ ] Every successful upward numeric-realm transition retains existing
      technique investment and lifetime realized cultivation, records a new
      source/target backing-group realm-entry record, and projects an empty main
      progress bar in the target realm without changing the unrefined bar.
* [ ] Training an earlier retained technique group after advancement increases
      lifetime realized cultivation but does not change the current realm's
      main progress bar.
* [ ] Techniques in the same group share one generated 1–13 layer curve using
      the corresponding player-family multiplier.
* [ ] Every generated curve has twelve positive integer transition costs whose
      largest-remainder normalization sums exactly to the configured mastered
      capacity and is reproducible across restarts/platforms.
* [ ] Every non-qi exact realm group accepts no more than five retained
      techniques; three mastered techniques back between `max_exp` and
      `max_exp + 2`, while the optional fourth/fifth provide additional backed
      cultivation redundancy.
* [ ] The shared qi group accepts no more than nine retained techniques, uses
      one common curve/cap rather than separate values for 练气一至十三层, and
      three mastered techniques retain exactly 11,295 cultivation.
* [ ] Player levels 练气十至十三 use `max_exp`
      `3,829 / 5,169 / 6,978 / 9,420`; their cumulative totals are
      `11,293 / 16,462 / 23,440 / 32,860`, so respectively three/five/seven/
      nine mastered qi techniques are sufficient without special post-mastery
      capacity.
* [ ] Tests load the selected Mortals-derived qi and level-14 technique fixtures,
      validate element/minimum-realm/effect content, and cover one-, three-,
      five-, and nine-technique settlement allocation including mid-settlement
      mastery.
* [ ] Technique fixtures validate and project layer-scaled typed effect values,
      but this task performs no live attack, control, buff, healing, casting,
      targeting, or cooldown mutation.
* [ ] Replacing/abandoning a technique subtracts exactly its destroyed invested
      cultivation, preserves only configured transferable cultivation, and
      recalculates realm progress atomically.
* [ ] Technique loss may drop a player across a major-realm boundary, and
      returning to that major realm requires a new authoritative breakthrough.
* [ ] Technique loss invalidates the first unsatisfied realm-entry record and
      every later record, rebuilds non-negative local progress from the last
      valid target-group baseline, and never lets a later re-advancement reuse
      an invalidated transition.
* [ ] Realm re-entry appends a new active generation/branch and restores
      retained target-group investment as local progress; inactive historical
      branches cannot block or satisfy the new active chain.
* [ ] Progress cannot advance past 元婴后期.
* [ ] Entering 元婴后期 retains historical investment/reserve and shows an empty
      main bar with `max_exp = 116,145,360`; accepted rewards can fill its
      reserve cap and level-22 seclusion can fill the bar, but a full bar never
      creates level 23 or hidden 化神 progress.
* [ ] A player at eligible 练气 levels 10–13 can start a 筑基 breakthrough and
      success transitions directly to level 14.
* [ ] Levels below 练气十层 cannot start the 筑基 breakthrough.
* [ ] An eligible 练气 player whose authoritative current-realm-local progress
      is below `max_exp` cannot start a 筑基 attempt; HUD fullness alone is not
      trusted.
* [ ] One-/two-/three-root players require exactly one 筑基丹 and receive a
      guaranteed eligible breakthrough when the cultivation-full condition is
      satisfied.
* [ ] Four-root success probability follows the configured quasi-exponential
      basis-point table and equals 100% at ten pills.
* [ ] Five-root success probability follows its separately configured steeper
      2/4/7/11/16/22/29/36/43/50% table, never exceeds 50%, and remains 50%
      at the ten-pill cap rather than becoming guaranteed; zero pills and more
      than ten pills are rejected.
* [ ] One-/two-/three-root and four-/five-root pill rules resolve through the
      same typed success-model interface without realm-service branches for
      specific spirit-root qualities.
* [ ] Every breakthrough rejects a source player whose current minor-realm
      progress is below the configured full `max_exp`.
* [ ] A failed four-/five-root attempt from levels 10–12 resolves exactly one
      frozen 50/50 secondary outcome: advance one optional 练气 layer or apply
      the fixed one-third source-level penalty.
* [ ] The optional-layer advance outcome changes only the numeric 练气 level:
      realized cultivation, every qi-technique investment, unrefined reserve,
      and retained-technique ownership remain unchanged; the new qi entry
      checkpoint makes the target layer's main progress bar empty.
* [ ] A failed level-13 attempt always applies the fixed one-third source-level
      penalty and never advances beyond 练气十三层.
* [ ] Failed later-major-realm breakthroughs always apply a fixed penalty equal
      to `floor(source_level.max_exp / 3)` from the attempted exact-level
      backing group.
* [ ] Players retaining any three through nine qi techniques at the same full
      source level lose the same aggregate cultivation. For levels 10–13 the
      fixed losses are `1,276 / 1,723 / 2,326 / 3,140`. The exact loss is randomly
      partitioned across all invested techniques in the relevant backing group,
      never makes an investment negative, and is settled atomically with the
      matching realized-cultivation reduction and realm recalculation.
* [ ] A fixed entropy fixture produces an exact golden per-technique debit
      vector through the HMAC-weighted, capacity-aware multi-round allocator;
      permuting input technique order does not change that vector.
* [ ] When a failure penalty leaves all realm-entry floors valid, the existing
      entry baseline is unchanged and local progress drops by exactly the fixed
      penalty. If a floor becomes invalid, the transition stack unwinds and
      rebuilds lower-realm progress without producing a negative value.
* [ ] In a later exact-level group, players retaining any three through five
      techniques at the same full source level also lose the same fixed
      aggregate; technique count changes only the random distribution, not the
      total, and realm recalculation may cross minor or major boundaries.
* [ ] Retrying or replaying a failed settlement reuses its frozen success roll,
      secondary outcome, penalty total, and per-technique debits; it cannot
      reroll or apply the loss twice.
* [ ] Changing the breakthrough catalog after a session starts does not change
      that session's frozen success probability, timing, or failure behavior.
* [ ] A persisted 10–15 minute breakthrough survives retries and cannot double
      consume pills or settle twice.
* [ ] While a breakthrough is pending, another breakthrough, ordinary
      seclusion, and technique abandonment/replacement/transfer are rejected;
      combat rewards may still increase reserve.
* [ ] Tests cover accepted, duplicate, offline, reconnect, competing-player
      pickup, level-up, early 筑基 from levels 10–13, pill-count validation,
      breakthrough success/failure, retry, restart, and cap behavior.

## Definition of Done

* Game Service progression catalog/state/API, minimal technique/area seclusion
  model, breakthrough session, and minimal 筑基丹 ownership/consumption changes
  are typed and migrated.
* Adapter response/presentation flow and owner-bound orb handling are tested.
* Python Ruff/tests and Java Gradle tests/build pass.
* Automated Game Service tests cover technique-ledger invariants, group-scoped
  realm progress, realm-entry rollback, seclusion allocation, reserve mutation
  boundaries, breakthrough probability/failure/idempotency, and cross-major
  realm regression.
* Local Paper smoke verifies kill -> authoritative reward -> visible orb -> HUD
  sync -> persisted reconnect state, plus seclusion selection presentation and
  post-transition main/reserve bar behavior.
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

Interpret each `max_exp` as the current-realm-local cultivation required to
fill that numeric level. Start level 1 at 100 and floor after every
multiplication. Level 22 has a fillable requirement representing the future
化神初期 cultivation floor, but no level-23 transition exists in this task.

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

Multiplier placement is deliberate: levels 10–13 use a smooth iterative ×1.35
curve instead of a separate level-13 ×3 spike. Their cumulative cultivation is
11,293 / 16,462 / 23,440 / 32,860, so three/five/seven/nine mastered qi
techniques respectively provide enough backing within the nine-technique cap.
Level 14's existing 43,931 value is retained as an explicit 筑基初期 balance
anchor rather than recalculated from the new level-13 value; this avoids
cascading changes to the already approved 筑基-through-元婴 table. The `max_exp`
on levels 16, 19, and 22 retains the high-cost ×4/×5/×6 cross-major floor
pattern. Level 22 uses that floor for fillable progress only. The 练气 -> 筑基
breakthrough may target level 14 from levels 10–13.

## Out of Scope (explicit)

* Potion/damage-over-time attribution fixes.
* 化神期 and any realm above 元婴后期.
* Authored/independent technique progression models, including 青元剑诀-style
  cross-realm layer tables, continuation-volume fusion unlocks, forced-training
  backlash, and parent-layer-derived slot-exempt branch techniques. This task
  implements only the common generated-curve technique model.
* Letting vanilla enchanting, Mending, commands, or unrelated XP mutate
  authoritative cultivation.
* Full technique combat effects, technique acquisition/content breadth,
  technique content-editor authoring, rich cultivation-area gameplay, pill poison, heart
  demons, and unrelated seclusion effects. This task includes only the minimal
  authoritative technique/area contracts and the player-facing seclusion
  selection GUI required for ordinary refinement.
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
* [`research/mortals-technique-system.md`](research/mortals-technique-system.md)
  — reference semantics for cultivation-backed technique investment,
  replacement/transfer loss, realm regression, compatibility, prerequisites,
  ordinary layer growth, typed effects, and future gaps explicitly deferred
  from this task: authored progression, fusion unlocks, and derived branches.
