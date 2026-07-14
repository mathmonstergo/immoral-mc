# Mortals numeric design reference for ImmortalMC

## Scope

This note extracts useful progression and cultivation balancing ideas from
`/home/adam/projects/mortals`. It is reference material, not a compatibility
contract. ImmortalMC remains server-authoritative, life-scoped, deterministic
at persistence boundaries, and driven by its own vertical-slice testing.

## Source files inspected

* `src/logic/player/linggen.py`
* `src/config/constants.py`
* `src/logic/progression/cultivation.py`
* `src/logic/progression/breakthrough.py`
* `src/config/data/items_dan.yaml`
* `src/logic/common/effect_utils.py`
* `docs/content_balance_world_design_20260326.md`
* relevant progression/effect tests

## Useful existing baselines

### Spirit-root tiers

The old project uses the following high-level cultivation-rate baselines:

| Old tier | Rate multiplier | Seclusion success | Deviation |
|---|---:|---:|---:|
| Celestial | 2.0 | 95% | 5% |
| Variant | 1.8 | 90% | 10% |
| True | 1.0 | 75% | 20% |
| Pseudo | 0.7 | 55% | 30% |
| None | 0.0 | 100% non-cultivator sentinel | 0% |

The generation implementation also uses weighted rarity and fixed five-element
plus mutated-element vocabularies. ImmortalMC already has a more granular
quality model (`quad`, `penta`, `triple`, `dual`, `variant`, `celestial`), so the
old tier probabilities should not be copied directly. The multipliers are useful
as an initial relative ordering and playtest baseline.

### Cultivation outcome formula

The old project combines:

* a random base gain;
* a level-based additive gain;
* spirit-root rate;
* location spirit density;
* pill-poison penalty;
* optional item success bonus and rate multiplier;
* success/failure/deviation branches.

Representative rules:

* cultivation item buffs: `success_bonus=0.10`, `rate_mult=1.15`;
* high-tier example: `success_bonus=0.40`, `rate_mult=1.50`;
* pill poison reduces positive cultivation gain by 1% per point, capped at 80%;
* deviation loses about 1.5 times the calculated gain and 0.5-1.0 lifespan;
* failed cultivation may lose up to roughly 15% of the calculated gain.

These are valuable content baselines, but the formula should be redesigned in
fixed-point units. The old additive expression `rate + location_rate - poison`
makes multiplier semantics unclear and uses floats. ImmortalMC should separate
base gain, additive basis-point modifiers, multiplicative modifiers, and clamps.

### Breakthrough potential

The old major-breakthrough flow uses:

* a required cultivation threshold;
* pill-granted potential (`+2..+6` per Foundation Establishment Pill);
* spirit-root bonuses (`+35` or `+60` for better roots);
* success probability equal to the final potential percentage;
* failure reducing potential by 5 points.

The product idea is useful: preparation items, root quality, and repeated failure
all affect breakthrough chance. The storage model should not reuse the mutable
single `potential` column. ImmortalMC should keep an immutable base chance/score,
append item/status modifiers with explicit scope, and record each breakthrough
attempt as an authoritative transaction when that feature is implemented.

### Effect scopes already demonstrated

The old content proves three useful effect lifetimes:

* persistent player/life changes, such as pill poison or accumulated potential;
* timed/tick-limited cultivation buffs;
* next-cultivation or next-breakthrough effects.

Element restrictions and tier/level restrictions are also already present in
content configuration. These map cleanly to the agreed ImmortalMC scopes:
`permanent_life`, `timed`, and `next_action`.

### Realm and experience curve

The old `LEVELS_INFO` grows early minor-stage experience by about 1.5x, then uses
larger realm-stage multipliers (roughly 1.65-1.8x). Lifespan jumps at major realm
boundaries (about 100 -> 200 -> 500 -> 1000 -> 2000+), while movement/combat
speed was later identified as too explosive.

Useful lessons:

* store only current progression facts on the life;
* keep realm names, required experience, lifespan targets, and baseline ratios in
  version-controlled definitions;
* do not persist `max_exp` or display names redundantly;
* establish experience/time-to-realm targets before copying raw thresholds;
* cap speed and percentage stacking so progression does not collapse into a
  single dominant attribute.

### Content and balancing practices worth retaining

* Stable item IDs and data-driven YAML definitions.
* Rolled item-instance effects remain fixed after generation.
* Effects record source and restrictions instead of directly overwriting player
  base attributes.
* Balance documents define target encounter duration and win-rate bands rather
  than tuning numbers without outcome targets.
* Percentage effects need per-source and total-stack caps.

## Schema implications for ImmortalMC

### Immutable base facts

`life_spirit_roots` should hold stable codes and the generator version. If base
cultivation rate or base breakthrough chance is persisted, use fixed-point
integer units (basis points), never `FLOAT`.

### Mutable cultivation state

Future `life_cultivation_states` should hold current realm/stage, accumulated
cultivation, pill poison, heart-demon state, age/lifespan facts, and a revision.
Definition-derived fields such as realm display name and required experience do
not belong in the player row.

### Effects and attempts

Future `life_cultivation_effects` should record source, stat, modifier type,
fixed-point value, scope, remaining uses, timing, stacking key, and status.
Breakthrough attempts should become their own authoritative records when that
vertical slice is implemented; they should consume `next_action` effects and
apply success/failure outcomes in one transaction.

### Analytics and recaps

Technical request/idempotency rows are not gameplay analytics. Future life or
annual recaps should be derived from domain facts/events such as cultivation
sessions, breakthroughs, deaths, completed quests, boss kills, and item history.

## Initial recommendation

Use the old numbers as playtest seeds, not final balance:

* relative root rate ordering around `0.7x`, `1.0x`, `1.8x`, `2.0x`;
* ordinary cultivation item bonus around `+10%` success and `1.15x` rate;
* rare/high-tier bonus up to about `+40%` success and `1.50x` rate, subject to
  caps and scarcity;
* pill-poison penalty concept retained, but exact accumulation and cap tested in
  Minecraft time/session pacing;
* realm experience curve retained only as a shape, then recalibrated against
  target real playtime per stage.

Before implementing cultivation numbers, define target player-hours for early
realm progression and target success/failure experience. Minecraft session
length and active gameplay differ too much from a chat bot to copy elapsed-time
values unchanged.
