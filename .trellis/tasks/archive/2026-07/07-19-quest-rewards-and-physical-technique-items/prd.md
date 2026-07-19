# brainstorm: Quest Rewards and Physical Technique Items

## Goal

Add a production-grade reward and physical-item flow that closes the first
playable cultivation loop: quests can grant configured items or cultivation,
players see and use real Minecraft items, technique manuals can be acquired
from loot, crafting, or quests, and quest delivery consumes matching items from
the player's actual inventory.

## What I Already Know

* Quest definitions currently have objectives but no reward definitions.
* Quest turn-in currently consumes PostgreSQL `life_item_stacks`; it does not
  inspect or mutate the Bukkit player inventory.
* The current Paper `grant-item` command changes only the Game Service stack.
* The installed Citizens 2.0.43 build has `ShopTrait`, a `TRADER` shop type,
  item-taking actions, and a purchase event.
* ImmortalMC currently consumes bound Citizens right-clicks for quest routing
  and does not integrate Citizens shop transactions.
* The cultivation GUI already lists authoritative learned `LifeTechnique`
  records, but production code has no learn/create path.

## User Decisions

* Quest rewards may contain a configured item and/or cultivation amount.
* Quest reward calculation must not use area, realm, lifespan, or cultivation
  speed/yield modifiers.
* A future explicit VIP multiplier is the only requested reward multiplier.
* Technique acquisition should use a physical Minecraft item obtainable from
  monster loot, crafting, or quest rewards.
* Consuming the technique item learns/unlocks the technique, after which it is
  visible in the cultivation GUI.
* Quest item delivery should consume the player's actual inventory items.
* This is a disposable-data development environment. Redesign the current
  model directly; do not add compatibility, migration, dual-read, or fallback
  behavior for old development data.

## Assumptions (Temporary)

* Quest cultivation rewards enter unrefined cultivation so the seclusion loop
  remains meaningful. The configured amount is fixed and is never silently
  truncated when the reserve is full; a durable pending reward remains
  claimable until it can be applied.
* A technique manual identifies one exact `technique_id` and creates an active
  learned technique at layer 0; generic choose-one manuals can be added later.
* The first slice should use a trader-style quest hand-in UI, but ImmortalMC
  should own the authoritative transaction rather than delegate it to a raw
  Citizens shop action.

## Open Questions

* Are technique manuals always tied to one exact technique, or can some open a
  choose-one-technique selection? The first slice assumes exact technique IDs.
* Are custom physical items freely transferable, or initially soulbound to the
  current life? The first slice assumes current-life ownership validation.

## Requirements (Evolving)

* Define typed quest rewards with stable reward IDs and deterministic order.
* Support physical item grants and cultivation grants in one quest.
* Freeze the actual reward result into the idempotent turn-in response.
* Apply fixed configured values. Do not call area, realm, lifespan, seclusion,
  or combat reward scaling policies.
* Credit quest cultivation into the unrefined reserve. If the reserve cannot
  accept it, retain a pending, idempotent reward grant instead of truncating or
  losing it.
* Preserve a single explicit extension point for a future VIP multiplier.
* Persist reward ledger/grant records in the same Game Service transaction as
  quest completion.
* Represent custom Minecraft items with stable Game Service item identity and
  PDC metadata in Paper. Paper must submit identity, not trusted reward values.
* Quest delivery validates authoritative ownership and exact item identity,
  then consumes the corresponding physical inventory items.
* Technique-item redemption atomically consumes the authoritative item and
  creates an active `LifeTechnique` with zero investment and layer 0.
* Duplicate use, duplicate turn-in, network retry, Paper restart, inventory
  full, player logout, and stale-life cases must not duplicate or lose rewards.
* Citizens may provide the NPC and trader-shaped UI, but Game Service remains
  authoritative for objective validation, item ownership, rewards, and quest
  completion.
* Update the Simplified Chinese public Wiki in the same change.

## Acceptance Criteria (Evolving)

* [ ] A quest can grant an item reward, a cultivation reward, or both.
* [ ] Replaying the same turn-in returns the same reward result without a
      second item grant or cultivation credit.
* [ ] Area and player realm changes do not change a quest's configured reward.
* [ ] The rewarded physical item appears in the player's inventory or remains
      durably claimable when no slot is available.
* [ ] A delivery quest removes the exact configured physical items from the
      player's inventory and never partially completes.
* [ ] A technique manual obtained from a quest can be consumed once and the
      learned layer-0 technique appears in `/immortal seclusion`.
* [ ] Citizens trader-style interaction cannot bypass Game Service validation.
* [ ] Python, Java, PostgreSQL integration, Wiki, and real Paper smoke checks
      pass.

## Definition of Done

* Tests added or updated at domain, repository, API, Paper adapter, and
  recovery-boundary levels.
* Lint, type checking, builds, and test suites pass.
* Player-, operator-, content-author-, and API-visible behavior is documented
  in Simplified Chinese under `docs/wiki/`.
* Failure recovery and idempotency are exercised with fixed operation IDs.

## Out of Scope

* Sect systems.
* Vanilla advancement replacement.
* VIP entitlement implementation; only a clean reward-policy extension point
  may be retained.
* Compatibility with existing development item-stack data.
* Full production content for every monster drop and crafting recipe in the
  first vertical slice.

## Technical Notes

* `game-service/src/immortal_mmo/quest/models.py`: no reward field today.
* `game-service/src/immortal_mmo/quest/service.py`: turn-in only consumes
  logical stacks and marks progress completed.
* `game-service/src/immortal_mmo/item/`: current quantity-only logical stack
  model needs redesign or a physical item-instance boundary.
* `game-service/src/immortal_mmo/cultivation/repository.py`: no learn-technique
  port exists today.
* `minecraft-nodes/main-plugin/.../citizens/`: quest clicks are routed and
  delayed-cancelled before Citizens default interaction.
* Local Citizens jar exposes `ShopTrait.ShopType.TRADER` and uses Bukkit
  Merchant recipes, but the purchase event is not a cancellable Game Service
  transaction boundary.
