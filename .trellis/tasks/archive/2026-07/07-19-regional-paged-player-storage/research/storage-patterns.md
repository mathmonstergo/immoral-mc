# Storage Patterns Research

## Existing project patterns

* Cultivation uses stable semantic `area_id` values and keeps coordinate
  resolution in Paper while Game Service validates the catalog and rules.
* Existing mutation APIs use UUID idempotency keys, frozen responses, and
  repository-level transactions.
* The project explicitly rejects Paper-local authority and fallback state.

## Recommended storage shape

Use a slot-level authoritative table keyed by current-life, stable area ID,
page, and slot. Store a canonical item-instance ID plus immutable item
template/version metadata. Keep a container revision incremented by each
successful move. Every move submits source/destination coordinates, expected
revision, item-instance identity, and operation UUID; the server verifies all
facts under deterministic row locks.

The Paper GUI should render a page snapshot and treat inventory clicks as
requests, not authoritative local commits. On success it applies the frozen
server snapshot. On conflict or timeout it closes/refetches instead of guessing
which item won.

## Failure handling

Because Bukkit inventory state and PostgreSQL cannot share an ACID transaction,
the adapter needs an operation journal/reconciliation path. Never remove an
item permanently before the server records the operation, and never grant a
second item merely because a response was lost. Stable item-instance IDs and
replayable operation IDs make reconnect reconciliation deterministic.

