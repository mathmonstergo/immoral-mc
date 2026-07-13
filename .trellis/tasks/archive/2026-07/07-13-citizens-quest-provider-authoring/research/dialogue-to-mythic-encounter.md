# Dialogue-to-MythicMob encounter transitions

## Goal

Explore how an actor can talk to a player before revealing a monster form and
starting combat, while preserving ImmortalMC's authority boundaries.

## Verified MythicMobs capabilities

The current official MythicMobs wiki documents the pieces needed for a
pre-combat state machine:

* `~onSignal:<signal>` triggers a metaskill when a mob receives an external
  signal.
* `setAI{ai=false|true}` disables or enables the mob's base AI.
* `runaigoalselector` and `runaitargetselector` can clear and replace goals and
  targets at runtime.
* `setstance{stance=<name>}` plus the `stance` condition supports named phases
  such as `dialogue`, `transforming`, and `combat`.
* `disguise`, `undisguise`, and `DisguiseModify` can change the visible form of
  the same MythicMob. They require LibsDisguises.
* MythicMobs supports active spawn through its API and exposes spawn/death/
  despawn events for encounter bookkeeping.
* `~onInteract` exists, but ImmortalMC should keep dialogue and quest decisions
  in its own Adapter/Game Service flow instead of duplicating them in Mythic
  YAML.

Important limitation: a disguise changes presentation, not the underlying mob
template or authoritative Game Service identity. The underlying MythicMob type,
base Bukkit entity, hitbox choices, and encounter identity already exist before
the reveal.

## Approach A: one MythicMob, human disguise, signal-driven reveal

The actor is a MythicMob from the beginning:

```text
spawn MythicMob encounter actor
  -> stance=dialogue
  -> AI disabled, no target, incoming damage cancelled
  -> human/player disguise
ImmortalMC dialogue finishes
  -> Adapter signals BEGIN_COMBAT
Mythic ~onSignal:BEGIN_COMBAT
  -> stance=transforming
  -> particles/sound/animation
  -> remove or replace disguise
  -> enable AI and combat target selectors
  -> stance=combat
```

### Strengths

* Same ActiveMob/encounter identity for the entire scene.
* Smooth reveal without despawn/spawn flicker.
* Mythic stance, signal, disguise, AI, threat, and phase tools fit naturally.
* Good for an enemy who is fundamentally a monster but initially masquerades as
  a human, statue, animal, or harmless creature.

### Costs and risks

* Human appearance normally adds LibsDisguises or ModelEngine.
* The base entity and hitbox exist before the reveal.
* Pre-combat damage must be synchronously cancelled; AI-off alone is not
  invulnerability.
* This actor is not a normal Citizens-managed persistent quest NPC.
* Restart/reload recovery must reconstruct whether it was in dialogue or combat.

## Approach B: Citizens actor swapped for a MythicMob

The actor begins as a normal Citizens NPC bound to an ImmortalMC encounter
template:

```text
Citizens NPC interaction
  -> ImmortalMC/Game Service dialogue and eligibility check
  -> Game Service authorizes encounter start and returns encounter ID
Adapter captures NPC persistent UUID + location + orientation
  -> play transformation VFX
  -> despawn/hide (never delete) Citizens NPC
  -> spawn configured MythicMob internal name at the same location
  -> index ActiveMob under encounter ID
MythicMob death/despawn/timeout
  -> report authoritative outcome
  -> clear encounter state
  -> respawn/show Citizens NPC according to policy
```

### Strengths

* Clean ownership: Citizens owns the dialogue actor; Mythic owns the fight.
* No disguise dependency is required for the pre-combat NPC.
* The combat entity can use the exact desired Mythic template, base type, model,
  hitbox, AI, skills, and boss configuration.
* Fits existing selected-Citizens-NPC authoring and persistent UUID binding.
* Best for a known NPC who betrays the player, transforms, or summons a battle
  form.

### Costs and risks

* It is an entity swap, so VFX must hide the transition.
* Requires careful rollback when Mythic spawn fails.
* Disconnect, server restart, chunk unload, mob despawn, and plugin disable must
  not leave the Citizens NPC permanently hidden.
* Shared-world concurrency must define whether one player starts the fight for
  everyone or receives a private/instanced encounter.

## Approach C: MythicMob NPC for the whole lifecycle

MythicMobs' official NPC guide uses an `INTERACTION` base entity, persistent
despawn policy, and a player disguise or ModelEngine model. ImmortalMC could bind
dialogue directly to that Mythic actor, then signal combat.

This avoids Citizens entirely for that actor. It is appropriate for temporary
or encounter-only characters, but it should not replace Citizens for ordinary
quest givers because it creates a second NPC lifecycle/identity system.

## Recommendation

Support two explicit encounter actor types rather than forcing every scene into
one mechanism:

1. **Persistent NPC reveal** — use Approach B. Bind an encounter template to a
   selected Citizens NPC, then swap it for a MythicMob during combat.
2. **Talking monster / disguised enemy** — use Approach A or C. Spawn a
   MythicMob in `dialogue` stance and reveal it through an ImmortalMC-issued
   signal.

For the user's described “talk, transform, fight” story attached to an existing
Citizens NPC, the user selected Approach B for future implementation. The
transformation VFX will make the swap look continuous while keeping plugin
responsibilities clear.

## Proposed future encounter template

```yaml
id: hidden-demon-encounter
dialogue-id: hidden-demon.intro
actor-type: citizens-swap
mythic-mob-id: immortal_hidden_demon_t1
begin-signal: BEGIN_COMBAT
transform-vfx: demonic-reveal
completion-policy: restore-citizens
failure-policy: restore-citizens
```

The template is presentation/orchestration data. Game Service owns eligibility,
encounter state, authoritative combat results, rewards, and quest progress.

## Required encounter state

* stable encounter ID and revision
* initiating player/party
* Citizens persistent NPC UUID, if applicable
* Mythic internal mob ID and ActiveMob/Bukkit instance UUID
* state: `dialogue|transforming|combat|completed|failed`
* original location/orientation and restore policy
* timeout and cleanup generation token

## Failure and concurrency matrix

| Condition | Required behavior |
|---|---|
| Dialogue cancelled/player leaves | Keep or restore Citizens actor; do not spawn mob |
| Game Service rejects start | Keep actor in dialogue state |
| MythicMobs missing/template absent | Fail closed and restore Citizens immediately |
| Mythic spawn throws/fails | Restore Citizens and mark encounter failed |
| Server/plugin stops during combat | Persist/reconcile encounter or restore NPC on next boot |
| Mob despawns without valid completion | Treat as failure/timeout, never as a rewardable kill |
| Duplicate start request | Return/join the existing encounter; do not spawn twice |
| Multiple players interact | Follow an explicit shared or instanced encounter policy |

## Sources

* Official MythicMobs wiki repository, current checkout:
  * `Guides/Making-an-NPC.md`
  * `Mobs/Disguises.md`
  * `Skills/Triggers/onSignal.md`
  * `Skills/Mechanics/signal.md`
  * `Skills/Mechanics/setai.md`
  * `Skills/Mechanics/runaigoalselector.md`
  * `Skills/Mechanics/runaitargetselector.md`
  * `Skills/Mechanics/setstance.md`
  * `Skills/Mechanics/disguise.md`
  * `Skills/Mechanics/undisguise.md`
* Existing project research:
  `.trellis/tasks/archive/2026-07/07-13-plugin-integration-research/research/mythicmobs-integration.md`
