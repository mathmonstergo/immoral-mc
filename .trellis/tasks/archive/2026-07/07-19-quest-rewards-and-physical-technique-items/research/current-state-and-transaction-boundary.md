# Current State and Transaction Boundary

## Repository Findings

* `QuestDefinition` contains objectives, providers, dialogue keys, and
  presentation hints, but no rewards.
* Quest turn-in uses one Game Service transaction to debit
  `life_item_stacks`, complete progress, increment revision, and freeze the
  HTTP response.
* The frozen response has no reward projection.
* Cultivation resource entries have a combat reward type, but no quest reward
  type. The combat credit path requires a kill event and cannot be reused as a
  generic quest credit.
* Paper has no physical item catalog, PDC codec, inventory scanner, item
  delivery inbox, or item-consumption recovery journal.
* The administrator `grant-item` command only calls the Game Service adjustment
  API and never inserts a Bukkit `ItemStack`.
* Learned techniques are queried and rendered by the seclusion GUI. Production
  code can abandon or transfer a technique but cannot create/learn one.

## Citizens Capability

The installed Citizens 2.0.43 build includes:

* `ShopTrait`
* `ShopTrait.ShopType.TRADER`
* a trader viewer implemented with `Bukkit.createMerchant`
* `ItemAction.take(...)` for inventory costs
* `NPCShopPurchaseEvent`

This proves Citizens can display a native merchant-shaped shop and take Bukkit
items. It does not make Citizens a suitable authority for an ImmortalMC quest
turn-in: its purchase event does not provide the Game Service transaction,
frozen idempotent result, cross-process recovery, or cultivation reward ledger.
The current ImmortalMC quest binding also delayed-cancels a handled Citizens
right-click, so a bound quest NPC will not transparently fall through to its
default Citizens shop.

## Recommended Boundary

Use Citizens for NPC identity and trader-shaped presentation. Use ImmortalMC
Paper code to collect stable physical item identities and call a Game Service
quest command. Game Service must validate the current life, quest state,
authoritative item ownership, item templates, technique eligibility, and reward
policy.

Physical inventory and PostgreSQL cannot share an ACID transaction. Avoid a
best-effort "remove then HTTP" or "HTTP then remove" flow. Give physical items
stable identities in PDC, record authoritative item/grant state in Game Service,
and use idempotent operations plus reconciliation/recovery on Paper. A
deterministic item/grant identity lets a retry detect an already-delivered item
instead of duplicating it.

For a technique manual, the clean redemption transaction is:

1. Paper submits the exact item instance identity and an operation ID.
2. Game Service locks the current life and item, validates the technique
   catalog and eligibility, marks the item consumed, and inserts a layer-0
   learned technique in one transaction.
3. Paper removes the matching PDC item and refreshes the learned-technique GUI.
4. Restart reconciliation removes a stale physical projection or delivers a
   missing one according to the authoritative operation result.

