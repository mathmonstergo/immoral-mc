# brainstorm: Regional Paged Player Storage

## Goal

Provide each player's current life with authoritative storage chests that are
separated by configured region and presented as a paged large-chest GUI. A
player can open the storage belonging to the region they are currently in,
move real custom items through a familiar Bukkit inventory, and later retrieve
those items in the same region without mixing inventories across regions.

## What I Already Know

* The Game Service currently stores quantity-only logical item stacks and has no
  slot-based inventory or storage module.
* Paper has a cultivation selection inventory but no persistent player storage
  GUI, page controller, or storage API.
* Cultivation regions are already represented by stable semantic `area_id`
  values resolved by Paper and validated by Game Service.
* The project is in disposable development phase: old data can be deleted and
  the storage schema can be introduced directly without compatibility paths.

## Product Decisions

* Storage is per current life and per region, not one global cross-region bag.
* The user-facing form is a large chest with pages; page navigation is explicit
  and cannot expose another region's contents.
* The region key is the stable Game Service `area_id`, not a raw world name or
  coordinate string.
* Game Service owns slot contents, item identity, capacity, permissions,
  locking, and persistence. Paper owns only GUI projection and Bukkit events.
* Storage is a container, not a quest or cultivation reward multiplier. It does
  not apply area, realm, lifespan, VIP, or stack-value transformations.
* Physical custom items use stable item-instance identity and PDC metadata;
  storage moves instances, not trusted display names or arbitrary quantities.

## Assumptions (Temporary)

* First slice uses 54 slots per page (a large chest), with 45 item slots and 9
  navigation/status slots.
* A default region storage has 9 pages (405 item slots); the capacity is a
  configuration/catalog value and can grow later without changing item IDs.
* Access requires the player to be physically inside the target region and to
  have the configured storage permission. Operators may inspect or repair via a
  separate administrative API later.
* Only one storage session per player is open at a time. Page changes and slot
  moves use idempotency keys and optimistic revision checks.

## Open Questions

* Should a region storage be shared among all lives on an account, or remain
  strictly current-life scoped? MVP assumes current-life scoped.
* Should storage allow remote access after a player has visited a region, or
  require being inside that region for every open/page/move operation? MVP
  requires presence for every mutation and page read.
* What should happen when a region is disabled or its page count changes? MVP
  rejects new access and preserves data; no automatic relocation.

## Requirements (Evolving)

* Add a typed storage catalog keyed by stable `area_id`, with page count,
  permission, and slot limits.
* Add PostgreSQL slot records keyed by `(life_id, area_id, page, slot)` and
  authoritative item-instance records or references.
* Expose idempotent open/snapshot and move operations with a monotonically
  increasing storage revision.
* Move operations must lock source/destination slots in deterministic order,
  validate current-life and region access, and atomically swap/move items.
* Reject stale revisions without deleting or duplicating an item.
* Paper resolves the current `area_id`, opens a 54-slot large-chest GUI, renders
  one page, and keeps navigation off the item-slot range.
* GUI close, disconnect, server restart, full inventory, and failed network
  calls must converge without item loss or duplication.
* Storage must integrate with physical item delivery and technique manuals;
  storing/retrieving an item preserves its exact PDC identity.
* Add Simplified Chinese Wiki documentation for region rules, capacity,
  commands/permissions, GUI controls, configuration, and troubleshooting.

## Acceptance Criteria (Evolving)

* [ ] Two regions for one life show independent inventories.
* [ ] Page navigation shows exactly the requested page and never leaks another
      region or player's contents.
* [ ] Moving an item between player inventory and storage is atomic and
      idempotent under retries.
* [ ] A stale page revision is rejected and the client refreshes safely.
* [ ] A player outside the region cannot open or mutate that region's storage.
* [ ] A full player inventory leaves the storage item in place or uses a
      durable pending return; it never deletes the item.
* [ ] Restart and reconnect preserve all stored item instances and revisions.
* [ ] The GUI works with a physical technique manual and preserves its exact
      identity.
* [ ] Python, Java, PostgreSQL integration, Wiki, and Paper smoke checks pass.

## Definition of Done

* Domain, repository, API, concurrency, and Paper GUI tests cover the complete
  move/read/retry lifecycle.
* No compatibility migration, dual-write, or fallback logical-stack path is
  retained for old development data.
* Public Wiki pages are updated and linked from `docs/wiki/index.md`.

## Out of Scope

* Cross-account guild/shared storage.
* Remote access, ender-chest semantics, sorting, search, auto-deposit, or
  mailbox/auction features.
* Citizens ShopTrait as storage authority.
* Automatic migration from current `life_item_stacks` into slot storage.

## Technical Notes

* Reuse the existing cultivation `area_id` catalog and Paper cuboid resolver;
  do not duplicate coordinate-to-region business rules in Game Service.
* The API must carry account/life identity and an idempotency key; it must not
  trust client-submitted region rewards, item counts, or slot contents.
* The storage UI is a new Paper listener/controller, separate from the
  cultivation seclusion holder and quest interaction state.

