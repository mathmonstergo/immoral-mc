# Current Quest GUI and Inventory-Objective Contract

## Paper interaction flow

Citizens right-clicks route through the stable persistent NPC UUID, prefer the
quest-provider binding, apply a player/NPC debounce, then call
`QuestProviderInteractionAction` and `QuestRequestCoordinator.refresh`.
Currently a single offer uses dialogue plus a second-right-click confirmation,
a ready quest immediately turns in, and multiple actionable quests only show a
placeholder. The custom GUI should replace those presentation branches while
reusing the request coordinator.

The regional-storage holder/controller is the strongest existing GUI lifecycle
pattern: account/life/provider identity, generation-based stale-response
rejection, current-holder checks, busy mutation locking, click/drag
cancellation, and quit/disable cleanup. The seclusion GUI is useful for item
rendering but does not have sufficient asynchronous lifecycle protection.

## Existing backend support

The interaction-state response already contains ordered provider quest
projections with quest ID, title, category, state, action, dialogue key, and all
objective rows. Existing accept and turn-in endpoints are sufficient; no
confirm or detail endpoint is required. Paper already scans physical inventory
instance IDs at turn-in, and Game Service revalidates exact life ownership,
`owned/inventory` state, item code, required quantities, and idempotency in one
Unit of Work. Extra and unrelated items remain untouched; any shortage rolls
back the whole turn-in.

Useful optional DTO additions for a real detail view are quest description,
reward previews, and stable objective type. Item code does not need to cross to
Paper merely to submit, because Paper may continue sending all validated
physical inventory IDs and Game Service selects the required instances.

## Required correctness repair

`QuestRevisionVector.objectives` currently derives from cultivation revision
plus the number of inventory items. It can decrease when items leave inventory,
remain unchanged when one item code is replaced by another, and collide across
different states. Paper correctly rejects lower revision vectors as stale, so
the current formula can freeze an old scoreboard/material projection.

The clean zero-to-one repair is a true monotonic per-life inventory/objective
input revision, exposed as an independent revision-vector component (or one
monotonic objective-input component). Inventory location/ownership mutations
must increment it. Do not replace the count with another hash or compatibility
fallback.

## Test focus

* Inventory quantity decrease and same-count item replacement advance revision
  and publish the new objective projection.
* GUI opened ready then inventory changed: submit fails atomically and refreshes.
* Multi-material excess/unrelated items consume only exact requirements.
* Concurrent different operation IDs complete/reward once.
* Same idempotency key and IDs replay; changed IDs conflict.
* Holder generation, busy state, close/quit/life replacement, provider rebind,
  and stale async responses cannot update or submit through an obsolete GUI.
