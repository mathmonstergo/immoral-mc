# Mortals technique-system reference

## Scope

Read-only review of `/home/adam/projects/mortals` to recover the intended
relationship among player cultivation, technique progression, compatibility,
replacement, realm loss, and configured effects.

## Authoritative relationship

Mortals does not treat player cultivation and technique cultivation as two
unrelated rewards:

* `cultivation._apply_gongfa_progress` first determines how much positive
  cultivation fits before the selected technique reaches layer 13.
* It returns only that applied amount for `add_player_exp`; overflow at the
  technique cap is not added to player cultivation.
* Positive cultivation from other flows is distributed across equipped
  techniques, while the same total is credited to the player.
* The intended domain invariant is therefore that retained technique
  investment backs realized player cultivation.

ImmortalMC should express this more strictly: technique-investment ledger
entries are the auditable source of realized cultivation, while the player's
realized total is a transactionally maintained aggregate/projection. A
seclusion consumes reserve once and credits only cultivation that can be stored
in the explicitly selected techniques.

## Replacement, abandonment, and transfer

Mortals computes a technique's total invested cultivation from completed layer
requirements plus current layer progress. On replacement:

* without a transfer item, the old investment is destroyed;
* with a transfer item, `keep_ratio` moves part of the old investment to the
  target technique, subject to transfer constraints such as tier and matching
  elements;
* player total cultivation is reduced by
  `old_total - actually_transferred_total`;
* the dedicated active-retraining path allows realm level to fall when the
  remaining cultivation no longer meets the current threshold.

ImmortalMC should perform technique removal/transfer, investment-ledger
entries, realized-total recalculation, and realm recalculation in one
authoritative transaction. The reference implementation's semantics are worth
keeping; its separated mutation calls should not be copied.

## Slots and seclusion selection

Mortals currently supports five technique slots. A technique cannot be freely
unequipped; it is replaced by learning or restoring another technique. Positive
multi-technique rewards are evenly divided in the old project.

The final user requirement intentionally changes allocation: there is no
persistent technique order. A Paper inventory GUI lets the player select one to
five concrete techniques for this seclusion. The selected ID/version set is
frozen for the session; a technique stops accepting cultivation once it reaches
layer 13.

When multiple selected techniques can accept cultivation, ImmortalMC uses an
equal water-filling allocator: split the gain evenly, remove techniques as they
reach capacity, and repeatedly redistribute their unused shares among the
remaining selected techniques. Integer remainders are assigned by stable
technique ID, never selection/click order.

Selected techniques must belong to the same major realm. Technique content
stores a cultivation-time weight matching the major-realm maximum-lifespan
ratio: 练气/筑基/结丹/元婴 = 1/2/5/10. Mortals' current player-facing seclusion
reference caps a full technique at 10% of maximum lifespan, giving approved
base mastery times of 10/20/50/100 in-game years for major-realm lifespan
anchors 100/200/500/1000.

The baseline clock is one in-game year per real-world hour. Cultivation areas
freeze two independent basis-point modifiers into the session: speed changes
the in-game years advanced per real hour, while yield changes effective
technique investment per unrefined cultivation consumed and may be greater than
1.0. Capacity-aware settlement never consumes reserve that cannot be retained.

## Attribute compatibility and prerequisites

Mortals technique content uses:

* `required_elements`: at least one configured element must intersect the
  player's canonical five-element spirit-root set; an empty list is universal;
* tier-to-minimum-realm mapping for cultivation eligibility;
* required equipped items (`require_equip_all` / `require_equip_any`);
* prerequisite technique layers;
* separate cultivation/action prerequisites where needed.

This supports a closed, typed prerequisite vocabulary rather than per-technique
service branches. ImmortalMC should preserve canonical element IDs and extend
the matcher deliberately for variant/celestial roots rather than parsing
display strings.

## Progress requirements

Mortals uses a shared exponential layer-cost template by coarse technique tier
and derives layers 1–13 from total invested cultivation. ImmortalMC uses the
shared geometric-curve idea for ordinary techniques but replaces Mortals'
coarse five-tier base table with the project's exact numeric realm catalog:

* 练气 techniques use one special shared group, while later techniques have the
  same exact numeric realm-level field as a player (14–22);
* techniques in the same group share one generated layer-cost curve;
* the curve's growth multiplier is the approved multiplier for that realm
  family: 1.5 for 练气, 1.7 for 筑基, 1.8 for 结丹, and 2.0 for 元婴;
* one mastered technique's capacity is `ceil(group_target / 3)`, so three
  mastered techniques provide a minimal non-negative tolerance over the target;
* cross-major multipliers are already reflected in the realm catalog's
  `max_exp` for levels 13, 16, and 19 and are not applied a second time inside
  the technique layer curve.

The later product decision replaces exact thirds with a minimal integer
tolerance: each technique capacity is `ceil(group_target / 3)`, so three
mastered techniques back between exactly the target and at most two cultivation
points above it. This avoids fractional storage while keeping the surplus
bounded and deterministic.

Technique retention also differs from Mortals' global five-slot design:

* 练气 techniques belong to one special shared group rather than numeric
  levels 1–13;
* every later exact realm level (筑基初期, 筑基中期, etc.) has its own group;
* the shared 练气 group retains up to nine ordinary techniques, while every
  later exact-realm group retains up to five ordinary techniques;
* three mastered techniques are only the sufficient cultivation baseline; the
  fourth and fifth provide optional backed-cultivation redundancy;
* old groups remain part of the player's retained cultivation history instead
  of competing for one global slot pool.

## 青元剑诀 and spanning inheritance techniques

Mortals contains `GF_QingyunJianjue_01` in
`src/config/data/items_gongfa.yaml`, but the current implementation does not
model the novel-inspired progression described for ImmortalMC. Its record is a
normal tier-1 technique with `required_elements: [木]`, generic effect growth,
and the same hard-coded thirteen-layer progression as other techniques. There
are no active fields for per-realm self-layer caps, fusion-based continuation,
parent/branch relationships, inherited branch layers, or slot-exempt derived
techniques.

Useful reusable pieces from Mortals are limited to:

* normalized prerequisite-technique-layer maps and separate cultivation/action
  prerequisite checks in `src/logic/progression/requirements.py`;
* generic item crafting/consumption transactions;
* transfer-item effects that persist a typed item policy and move a bounded
  fraction of old technique investment.

ImmortalMC therefore needs a separate authored inheritance-technique model,
not another ordinary group curve. The definition should support:

* explicit per-layer cultivation and training-time values;
* realm layer caps such as 3/6/9/12/13 for
  练气/筑基/结丹/元婴/化神;
* versioned segment unlocks produced by atomically consuming/fusing configured
  items;
* derived branch definitions linked by parent ID and unlock layer.

The fusion flow should follow Mortals' atomic item-deduction pattern but use a
dedicated technique-layer-unlock operation instead of crafting a second copy
of the technique item. It locks the learned technique and inventory, validates
the current unlock stage and realm, consumes the configured continuation item,
and records the unlocked segment in an auditable player-technique unlock
ledger.

A branch should normally be a derived projection rather than a second
cultivation ledger: its effective layer follows the parent, it contributes no
additional realized cultivation, it receives no seclusion allocation, and it
uses a slot-exempt policy. Parent abandonment or layer regression immediately
downgrades or disables the branch. This prevents duplicate cultivation backing
and avoids branches consuming the ordinary nine/five retention caps.

## Effects and content shape

`items_gongfa.yaml` demonstrates a useful content vocabulary:

* stable ID, localized name, description, category, tier/minimum level;
* required elements and other prerequisites;
* cast timing, cooldown, targets, and target rules;
* typed `effects_v2` entries for cost, triggered, persistent, status, healing,
  attack, defense, speed, aggro, and similar effects;
* per-layer growth and layer-based target-count changes;
* crafting data and acquisition value.

Representative initial test content copied by stable identity/name and adapted
to the new strict schema:

* shared qi group: `GF_YinqiShu_01` 引气术 (universal/support),
  `Gongfa_68726c` 冰冻术 (水/冰 attack-control), `Gongfa_b8d7e3`
  缠绕术 (木 control), `Gongfa_6fcf01` 地刺术 (土 attack), and
  `Gongfa_eff4d0` 火弹术 (火 attack);
* level-14 group: `GF_RanxueZhan_01` 燃血斩 (universal attack),
  `Gongfa_8c1470` 灵力针刺 (universal attack), and
  `Gongfa_Fenglie_01` 风裂遁刃诀 (风 attack/mobility).

ImmortalMC should reuse the separation of definition, prerequisites, cast
contract, and typed effects, but validate it strictly and keep effect execution
outside cultivation settlement.

## Files reviewed

* `src/logic/progression/gongfa.py`
* `src/logic/progression/cultivation.py`
* `src/logic/progression/requirements.py`
* `src/logic/progression/breakthrough.py`
* `src/logic/inventory/items.py`
* `src/config/items.py`
* `src/config/constants.py`
* `src/config/data/items_gongfa.yaml`
* `docs/玩法说明.md`
* relevant progression/content tests
