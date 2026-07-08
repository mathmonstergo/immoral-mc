# Paper Spirit Root Command

## Goal

Add a Paper Adapter command that lets a joined player request spirit-root
detection through the authoritative Game Service and displays the returned
result in Minecraft without implementing any spirit-root roll logic in Java.

## What I already know

* Game Service owns spirit-root generation and persistence.
* Existing endpoint: `POST /api/v1/players/{account_id}/current-life/spirit-root`.
* Existing response contains `life_id`, `spirit_root`, and `already_detected`.
* Variant roots are represented by Game Service with `elements`, optional
  `mutated_element`, and optional `variant_element`.
* Paper Adapter now caches successful login snapshots by Minecraft UUID.
* Existing command root is `/immortal` with subcommand `health`.

## Assumptions

* The command should be `/immortal spirit-root`.
* Only in-game players can use this MVP command because it needs the sender's
  Minecraft UUID.
* If the player has not synced through Game Service yet, the command fails
  closed and tells them to reconnect or wait for profile loading.
* The Adapter displays fields returned by Game Service but does not translate
  or recompute spirit-root rules.

## Requirements

* Add Game Service client support for spirit-root detection by `account_id`.
* Add Java response records for spirit-root detection.
* Extend `/immortal` command parsing with `spirit-root`.
* Pass player identity from the Bukkit command executor into command services.
* Look up the player's cached `account_id` from `PlayerSessionCache`.
* Call Game Service asynchronously and send final messages on the Paper main
  thread.
* Preserve existing `/immortal health` behavior.

## Acceptance Criteria

* [x] Java tests cover spirit-root HTTP request/response parsing.
* [x] Java tests cover command parsing for `spirit-root`.
* [x] Java tests cover missing player context and missing cached login state.
* [x] Java tests cover successful spirit-root display and failure display.
* [x] `/immortal health` tests still pass.
* [x] Plugin command wiring passes `PlayerSessionCache` to command services.
* [x] Local Gradle `test build` passes.

## Definition of Done

* Tests added or updated.
* Build/test commands run.
* Game Service authority remains respected.
* Specs updated if the command establishes new Adapter conventions.
* Work committed, task archived, and session recorded.

## Technical Approach

* Add `GameServiceClient.detectSpiritRoot(UUID accountId)`.
* Add `SpiritRootSnapshot` and `SpiritRootDetectionResult` records.
* Extend `ImmortalCommandAction` with `SPIRIT_ROOT`.
* Introduce a command sender context carrying optional Minecraft UUID.
* Add `SpiritRootCommandRunner` that uses `PlayerSessionCache` and
  `GameServiceClient`.
* Update `ImmortalBukkitCommandExecutor` to pass player UUID when the sender is
  a `Player`.

## Decision (ADR-lite)

**Context**: Spirit-root detection changes authoritative player progression
state and must not be rolled in the Adapter.

**Decision**: The Paper command only identifies the player, looks up the cached
Game Service account ID, calls the existing Game Service endpoint, and displays
the returned payload.

**Consequences**: The command depends on successful join login sync. If sync is
missing or Game Service is down, the command fails closed instead of generating
local state.

## Out of Scope

* GUI, particles, scoreboard, or custom text styling.
* Spirit-root generation probabilities or variant parsing logic in Java.
* Console/admin detection for arbitrary account IDs.
* Retry loops or persistent Adapter cache.

## Technical Notes

* Existing Game Service contract:
  `.trellis/spec/backend/quality-guidelines.md`
* Existing plugin command classes:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/command/`
* Existing session cache:
  `minecraft-nodes/main-plugin/src/main/java/com/immortalmc/adapter/session/PlayerSessionCache.java`
