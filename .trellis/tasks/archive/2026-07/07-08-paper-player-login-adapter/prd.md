# Paper Player Login Adapter

## Goal

Wire the Paper Adapter Plugin to the existing Game Service player login API so
Minecraft joins create or reload the authoritative Game Service account/current
life state without adding MMORPG business rules to Java.

## What I already know

* The Paper scaffold under `minecraft-nodes/main-plugin/` already builds
  against Paper `1.21.11` and has an async `/immortal health` command.
* Game Service already exposes `POST /api/v1/players/login`.
* Login request payload is `minecraft_uuid` plus `player_name`.
* Login response contains `account` and `current_life`.
* The next slice should prepare later spirit-root detection by knowing the
  player's authoritative `account_id`.
* The user is away and asked the agent to continue autonomously after the
  previous task.

## Assumptions

* This task should stay minimal: log in/sync on `PlayerJoinEvent`, cache the
  returned account/current-life snapshot in memory, and provide operator-visible
  feedback/logging.
* The Adapter may cache identifiers returned by Game Service for later command
  use, but Game Service remains the persistence authority.
* If Game Service login fails, the plugin should report the failure and avoid
  inventing local account/life state. It should not kick players in this MVP.

## Requirements

* Add a Game Service client method for `POST /api/v1/players/login`.
* Model the login request/response shapes in Java records.
* Register a Paper `PlayerJoinEvent` listener in the plugin lifecycle.
* On player join, call Game Service asynchronously; do not block the Paper main
  thread.
* Dispatch player-facing messages and Bukkit state updates back to the main
  thread.
* Cache successful login snapshots by Minecraft UUID for later adapter commands.
* Keep the Adapter boundary: no spirit-root generation, progression rules, or
  database decisions in Java.

## Acceptance Criteria

* [x] Java tests cover login request serialization and response parsing.
* [x] Java tests cover successful and failed join-login handoff without Paper
      runtime where practical.
* [x] Plugin registers a join listener from `ImmortalMainPlugin`.
* [x] Player join login uses `POST /api/v1/players/login` asynchronously.
* [x] Successful login stores account/current-life IDs in an in-memory adapter
      session cache.
* [x] Failed login reports a clear unavailable/failure message and does not
      create local fallback state.
* [x] `./gradlew` or local Gradle `test build` passes.

## Definition of Done

* Tests added or updated.
* Build/test commands run with current local constraints documented if needed.
* Game Service authority remains respected.
* Specs updated if this establishes new Adapter conventions.
* Work committed, task archived, and session recorded before moving on.

## Technical Approach

Add narrowly scoped Java components:

* `GameServiceClient.loginPlayer(...)` builds a JSON POST to
  `/api/v1/players/login` and parses the existing response contract.
* `PlayerSessionCache` stores successful login snapshots by Minecraft UUID.
* `PlayerJoinLoginService` owns the async login flow and dispatches final
  presentation to the Paper main thread.
* `ImmortalPlayerJoinListener` adapts Paper `PlayerJoinEvent` to
  `PlayerJoinLoginService`.
* `ImmortalMainPlugin` wires the cache, service, and listener.

## Decision (ADR-lite)

**Context**: The plugin needs to know which Game Service account maps to a
Minecraft player before later commands like spirit-root detection can call
account-scoped APIs.

**Decision**: Login on join and cache the returned authoritative snapshot in
memory. Do not persist in Java and do not block join handling on the main
thread.

**Consequences**: The server can keep accepting players if Game Service is
temporarily unavailable, but gameplay features that require authoritative
account state should fail closed until login succeeds.

## Out of Scope

* Spirit-root detection command or UI.
* Kicking players when Game Service login fails.
* Database persistence or new Game Service endpoints.
* Reconnect retry loops, idempotency keys, Redis, or event bus plumbing.
* Multi-server/Velocity session sync.

## Technical Notes

* Existing Game Service route:
  `game-service/src/immortal_mmo/player/api.py`
* Existing response schemas:
  `game-service/src/immortal_mmo/player/schemas.py`
* Existing integration tests:
  `game-service/tests/integration/test_player_api.py`
* Existing plugin scaffold:
  `minecraft-nodes/main-plugin/`
* Related spec:
  `.trellis/spec/backend/quality-guidelines.md`
