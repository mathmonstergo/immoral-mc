# Backend Quality Guidelines

> Review and test standards for Game Service work.

## Project-Specific Quality Bar

The backend is the authoritative MMORPG rules engine. Correctness matters more than making the Minecraft presentation "feel like it worked" locally.

Hard requirements:

* Adapter never decides trusted combat, loot, cultivation, reincarnation, or account progression outcomes.
* Game modules interact through service interfaces.
* Any deterministic gameplay formula gets direct tests.
* Any data file or generated content format gets schema validation.
* Any player lifecycle slice gets at least one integration or end-to-end test.

## Forbidden Patterns

* Business logic in FastAPI route handlers.
* Business logic in the Paper Adapter.
* Cross-module table access from repositories.
* Trusting damage, loot, breakthrough success, reincarnation status, or item eligibility values sent by the client/plugin.
* Silent fallback to default gameplay values when authoritative data is missing.
* Broad `except Exception` that returns success or hides failure.
* Adding a mature Minecraft plugin as a shortcut around Game Service authority.

## Required Patterns

* Thin route -> service -> repository flow.
* Pydantic schemas for API request/response boundaries.
* Explicit domain errors with stable codes.
* Transaction boundaries around multi-step state mutations.
* Tests written with readable examples, e.g. "100 attack vs 50 defense produces expected damage".
* Data-driven content where practical: items, mobs, quests, skills, and techniques should be schemas plus interpreters, not scattered `if id == ...` branches.

## Testing Requirements

Follow the architecture document's three-layer strategy:

1. Data/schema validation tests for configuration files and content.
2. Formula tests for deterministic combat, cultivation, item, and loot rules.
3. End-to-end tests for vertical player loops.

First vertical-slice tests should prove:

* account/life state can be created and reloaded
* spirit root detection persists to the current life
* a simple cultivation/progression action changes authoritative Game Service state
* API responses match schemas expected by the Adapter

## Review Checklist

Before marking backend work complete, verify:

* Does the change preserve Game Service authority?
* Did any module reach into another module's repository/table?
* Are all new API payloads typed with Pydantic schemas?
* Are domain failures mapped to stable error codes?
* Are database writes transactional where a partial write would corrupt game state?
* Are logs useful for tracing a player state transition without leaking secrets?
* Are tests present at the right level for the risk?
* Were docs/specs updated if a new convention was established?

## Initial Verification Commands

Run these from `game-service/`:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
```

The first scaffold uses `httpx2` in dev dependencies because current FastAPI/Starlette emits a deprecation warning when `TestClient` uses legacy `httpx`. Keep test output warning-free.

## Scenario: Health Endpoint Scaffold

### 1. Scope / Trigger

Trigger: backend scaffold creates the first Adapter-facing API contract.

### 2. Signatures

* Runtime command: `.venv/bin/python -m uvicorn immortal_mmo.main:app --reload`
* Test command: `.venv/bin/python -m pytest`
* Lint command: `.venv/bin/python -m ruff check .`
* API signature: `GET /health`

### 3. Contracts

`GET /health` response:

```json
{
  "service": "game-service",
  "status": "ok",
  "version": "0.1.0"
}
```

Fields:

* `service`: literal `"game-service"`
* `status`: literal `"ok"` while the process is accepting requests
* `version`: package/service version string

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Service running | `200` with the contract above |
| Unknown path | FastAPI default `404` |
| App import failure | Tests fail before deployment; do not hide import errors |

### 5. Good/Base/Bad Cases

* Good: `/health` returns the exact JSON contract and `/docs` returns HTTP 200.
* Base: health test imports `immortal_mmo.main:app` from the installed package.
* Bad: route returns plain text, omits version, or constructs a response shape outside a Pydantic model.

### 6. Tests Required

`game-service/tests/integration/test_health.py` must assert:

* HTTP status is `200`
* JSON payload equals the exact health contract

### 7. Wrong vs Correct

#### Wrong

```python
@app.get("/health")
def health():
    return {"ok": True}
```

This skips the versioned response model and produces an unstable shape for Adapter checks.

#### Correct

```python
@api_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return get_health()
```

The route stays thin and the response model defines the contract.

## Scenario: Player Login And Spirit Root Detection

### 1. Scope / Trigger

Trigger: first gameplay-facing Adapter contract for account/current-life creation and spirit root detection.

### 2. Signatures

* API signature: `POST /api/v1/players/login`
* API signature: `POST /api/v1/players/{account_id}/current-life/spirit-root`
* Service entry points:
  * `PlayerService.login(minecraft_uuid, player_name)`
  * `PlayerService.detect_current_life_spirit_root(account_id)`

### 3. Contracts

`POST /api/v1/players/login` request:

```json
{
  "minecraft_uuid": "00000000-0000-0000-0000-000000000000",
  "player_name": "Steve"
}
```

Response contains:

* `account.account_id`: generated UUID
* `account.minecraft_uuid`: request UUID
* `account.player_name`: request display name
* `current_life.life_id`: generated UUID
* `current_life.account_id`: same as `account.account_id`
* `current_life.generation_no`: `1`
* `current_life.status`: `"alive"`
* `current_life.spirit_root`: `null` before detection

`POST /api/v1/players/{account_id}/current-life/spirit-root` response:

```json
{
  "life_id": "uuid",
  "spirit_root": {
    "quality": "variant",
    "label": "异灵根",
    "elements": ["金"],
    "mutated_element": "金雷",
    "variant_element": "雷"
  },
  "already_detected": false
}
```

Spirit root generation is two-stage:

1. Roll quality bucket first:
   * `quad`: 30%
   * `penta`: 30%
   * `triple`: 20%
   * `dual`: 12%
   * `variant`: 5%
   * `celestial`: 3%
2. Draw elements after quality is known.

Variant roots draw from:

```python
["火风", "木风", "金雷", "水雷", "火雷", "水冰", "木冰", "金暗", "土暗"]
```

A variant string is one base five-element plus one variant attribute. Example: `"金雷"` means `elements: ["金"]`, `mutated_element: "金雷"`, `variant_element: "雷"`.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| New Minecraft UUID logs in | Create account and generation-1 life |
| Existing Minecraft UUID logs in again | Return same account and current life |
| Current life has no spirit root | Generate root and persist on current life |
| Current life already has spirit root | Return existing root with `already_detected: true` |
| Unknown account ID detects spirit root | `404` with `player.account_not_found` |
| Invalid UUID in path/body | FastAPI/Pydantic validation error |

### 5. Good/Base/Bad Cases

* Good: service owns the spirit root roll and stores the result on the current life.
* Base: API route is thin and delegates to `PlayerService`.
* Bad: Adapter or client sends `quality`/`elements`; Game Service trusts it.
* Bad: variant root returns `["金", "雷"]` as ordinary elements instead of splitting base and variant attributes.

### 6. Tests Required

API tests must assert:

* login creates account/current life
* login is idempotent by Minecraft UUID
* spirit root detection returns structured result
* repeated detection does not reroll
* unknown account returns structured domain error

Unit tests must assert:

* all quality buckets map to the intended labels and element counts
* variant root splits `mutated_element` into base `elements` and `variant_element`
* quality is chosen before element composition

### 7. Wrong vs Correct

#### Wrong

```python
root = request.spirit_root
life.spirit_root = root
```

This trusts client/plugin input for a progression-defining result.

#### Correct

```python
spirit_root = self._spirit_root_generator.generate()
updated_life = self._repository.set_current_life_spirit_root(account_id, spirit_root)
```

Game Service generates and stores the authoritative result.

## Scenario: Paper Adapter Health Command Scaffold

### 1. Scope / Trigger

Trigger: first Minecraft-side Paper Adapter plugin scaffold and first
operator-facing command that talks to Game Service.

### 2. Signatures

* Plugin module: `minecraft-nodes/main-plugin/`
* Gradle dependency: `io.papermc.paper:paper-api:1.21.11-R0.1-SNAPSHOT`
* Plugin descriptor: `src/main/resources/plugin.yml`
* Runtime config: `src/main/resources/config.yml`
* Minecraft command: `/immortal health`
* Game Service API called by the Adapter: `GET /health`

### 3. Contracts

`plugin.yml` must declare:

```yaml
name: ImmortalMC
main: com.immortalmc.adapter.ImmortalMainPlugin
api-version: '1.21.11'
commands:
  immortal:
    usage: /immortal health
```

`config.yml` must declare:

```yaml
game-service:
  base-url: "http://127.0.0.1:8000"
```

`/immortal health` behavior:

* sends an immediate "checking" message
* calls `GET /health` asynchronously
* sends success/failure back to the command sender on the Paper main thread
* never computes gameplay state or fallback gameplay results locally

The plugin may use `plugin.yml` `libraries:` for runtime-only Maven Central
libraries instead of shading them into the jar. Gradle still needs matching
dependencies on the compile/test classpath.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Game Service returns `200` health payload | Command reports service, status, and version |
| Game Service returns non-`200` | Command reports unavailable with HTTP status |
| Game Service returns invalid JSON | Command reports unavailable with invalid-response message |
| Game Service is unreachable | Command reports unavailable; plugin must not block the main thread |
| Unknown `/immortal` subcommand | Command reports `Usage: /immortal health` |
| Missing command in `plugin.yml` | Plugin enable fails loudly instead of silently running without the command |

### 5. Good/Base/Bad Cases

* Good: `JavaPlugin` only wires lifecycle/config/commands; HTTP access lives
  in a client class; command behavior is testable without Paper runtime.
* Base: automated tests cover command parsing, message formatting, HTTP health
  parsing, resource descriptors, and main-thread dispatch handoff.
* Bad: command executor calls `HttpClient.send(...)` on the Paper main thread.
* Bad: Adapter returns default success when Game Service is down.
* Bad: Adapter starts implementing cultivation, combat, loot, economy, or
  player progression rules in Java.

### 6. Tests Required

Java tests should assert:

* `/immortal health` resolves to the health action
* empty/unknown commands show usage
* health success and failure messages are stable
* health HTTP client parses the `/health` contract and rejects non-success
* async command runner dispatches final messages through the main-thread
  dispatcher
* `plugin.yml` declares the entrypoint, API version, command, and runtime
  libraries
* `config.yml` declares the default Game Service base URL

Build verification should include:

```bash
./gradlew --no-daemon --max-workers=1 test
./gradlew --no-daemon --max-workers=1 build
```

If the wrapper cannot download Gradle because of WSL/network constraints, use a
local Gradle `9.6.1` with the same tasks and document the wrapper download
failure separately from code/build failures.

### 7. Wrong vs Correct

#### Wrong

```java
public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
    HttpResponse<String> response = httpClient.send(request, BodyHandlers.ofString());
    sender.sendMessage(response.body());
    return true;
}
```

This blocks the Paper main thread and exposes raw API output to the player.

#### Correct

```java
healthCheckFuture.whenComplete((result, error) -> {
    scheduler.runTask(plugin, () -> sender.sendMessage(format(result, error)));
});
```

The HTTP request completes off-thread, then presentation returns to the Paper
main thread.

## Scenario: Paper Adapter Player Login Sync

### 1. Scope / Trigger

Trigger: Paper Adapter starts listening to player lifecycle events and calls an
account/life Game Service API.

### 2. Signatures

* Paper event: `PlayerJoinEvent`
* Adapter client method: `GameServiceClient.loginPlayer(UUID minecraftUuid, String playerName)`
* Game Service API: `POST /api/v1/players/login`
* Runtime cache: in-memory map keyed by Minecraft UUID

### 3. Contracts

Adapter request body:

```json
{
  "minecraft_uuid": "00000000-0000-0000-0000-000000000000",
  "player_name": "Steve"
}
```

Adapter response model:

* `account.account_id`
* `account.minecraft_uuid`
* `account.player_name`
* `current_life.life_id`
* `current_life.account_id`
* `current_life.generation_no`
* `current_life.status`
* `current_life.spirit_root`

Join behavior:

* calls Game Service asynchronously
* stores the returned authoritative snapshot in memory only after success
* dispatches cache writes and operational logs back to the Paper main thread
* writes success/failure details to Paper logs, not player chat
* does not kick the player in the MVP when login fails

The Java Adapter may cache returned IDs to support later adapter commands, but
it must not persist account/life state or generate gameplay state locally.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| New Minecraft UUID joins | Game Service creates account/current life; Adapter caches returned snapshot and logs `player_login_success` |
| Existing Minecraft UUID joins | Game Service returns existing account/current life; Adapter replaces cached snapshot and logs `player_login_success` |
| Game Service returns non-`200` | Adapter logs `player_login_failure` and leaves cache empty/unchanged for that join |
| Game Service returns invalid JSON | Adapter logs `player_login_failure` and does not create fallback state |
| Game Service is unreachable | Adapter logs `player_login_failure`; Paper main thread is not blocked |

### 5. Good/Base/Bad Cases

* Good: listener extracts `player.getUniqueId()` and `player.getName()`, then
  delegates to a testable service.
* Base: Java tests cover request serialization, response parsing, async
  dispatch, successful cache writes, and failed login with no fallback cache.
* Bad: listener performs blocking HTTP directly inside `onPlayerJoin`.
* Bad: Adapter creates local account IDs or life IDs when Game Service is down.
* Bad: Adapter sends spirit-root or progression decisions during login.

### 6. Tests Required

Java tests should assert:

* login request JSON uses `minecraft_uuid` and `player_name`
* login response maps `account` and `current_life` fields correctly
* successful join-login writes to `PlayerSessionCache` through the dispatcher
* successful join-login logs `player_login_success` and sends no lifecycle chat
* failed join-login logs `player_login_failure`, sends no technical chat, and does not cache fallback state
* plugin build compiles the Paper listener registration

### 7. Wrong vs Correct

#### Wrong

```java
@EventHandler
public void onPlayerJoin(PlayerJoinEvent event) {
    UUID accountId = UUID.randomUUID();
    localCache.put(event.getPlayer().getUniqueId(), accountId);
}
```

This invents authoritative player state in the Adapter.

#### Correct

```java
loginFuture.whenComplete((result, error) -> {
    scheduler.runTask(plugin, () -> {
        sessionCache.store(result);
        logger.info("player_login_success player_name=Steve minecraft_uuid=...");
    });
});
```

The Game Service owns account/life state; the Adapter stores only the returned
snapshot for later presentation-layer calls.

## Scenario: Paper Adapter Spirit Root Command

### 1. Scope / Trigger

Trigger: Paper Adapter exposes the first gameplay-facing command that changes
authoritative player progression state through Game Service.

### 2. Signatures

* Minecraft command: `/immortal spirit-root`
* Adapter client method: `GameServiceClient.detectSpiritRoot(UUID accountId)`
* Game Service API: `POST /api/v1/players/{account_id}/current-life/spirit-root`
* Required local state: successful join-login snapshot in `PlayerSessionCache`

### 3. Contracts

The command must:

* require an in-game player sender for the MVP
* resolve the sender's Minecraft UUID to cached Game Service `account_id`
* call Game Service asynchronously
* display the returned `quality`, `label`, `elements`, and optional
  `mutated_element` / `variant_element`
* preserve `/immortal health`

The Adapter must not:

* roll spirit-root quality or elements
* send client/plugin-provided spirit-root values to Game Service
* create local fallback progression state when Game Service is unavailable

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Console runs `/immortal spirit-root` | Player-only message |
| Player has no cached login snapshot | Fail closed with profile-not-loaded message |
| Game Service returns first detection | Display returned spirit root |
| Game Service returns already-detected result | Display returned spirit root without rerolling |
| Game Service returns non-`200` | Display unavailable message |
| Variant root has `mutated_element` / `variant_element` | Display those returned fields |

### 5. Good/Base/Bad Cases

* Good: command passes only `account_id` to Game Service and displays the
  returned payload.
* Base: tests cover command parsing, missing player context, missing cache,
  successful display, failure display, and HTTP response parsing.
* Bad: Java command contains probability tables or element-selection logic.
* Bad: Java command lets the player choose or submit a spirit root.

### 6. Tests Required

Java tests should assert:

* `spirit-root` resolves to a dedicated command action
* console sender is rejected
* missing profile cache fails closed
* successful detection uses cached `account_id`
* failed detection does not create fallback state
* variant response fields are displayed when present

### 7. Wrong vs Correct

#### Wrong

```java
SpiritRoot root = SpiritRootGenerator.roll();
player.sendMessage(root.label());
```

This moves progression-defining random generation into the Adapter.

#### Correct

```java
detectSpiritRoot.apply(session.account().accountId())
        .whenComplete((result, error) -> dispatchPresentation(result, error));
```

Game Service remains authoritative; the Adapter only identifies the player and
shows the returned result.

## Scenario: Paper Adapter Spirit Root Detector Entity Interaction

### 1. Scope / Trigger

Trigger: Paper Adapter turns the temporary command-driven spirit-root test into
a Wynncraft-style in-world interaction bound to a server-authored entity.

### 2. Signatures

* Minecraft player command: `/immortal spirit-root-detector set`
* Minecraft admin command: `/immortal spirit-root-detector reload`
* Paper event: `PlayerInteractEntityEvent`
* Config path: `content.spirit-root.detectors`
* Config entry fields:
  * `world`: Bukkit world name
  * `entity-uuid`: bound detector entity UUID
* Shared use case:
  `SpiritRootDetectionUseCase.detectForPlayer(UUID minecraftUuid, String logEventPrefix, Consumer<String> sendMessage, Consumer<SpiritRootDetectionResult> onSuccess)`
* Presentation planner:
  `SpiritRootParticlePlanner.plan(SpiritRootSnapshot root)`

### 3. Contracts

Detector authoring:

* `set` requires an in-game player sender.
* `set` saves the entity the player is looking at, not a block coordinate.
* `reload` reloads detector bindings from disk-backed config.
* Saved detector bindings remain reviewable as config data.

Detector interaction:

* Only right-clicking a configured detector entity triggers detection.
* The Adapter resolves the player through `PlayerSessionCache` and calls Game
  Service with only the authoritative `account_id`.
* Successful detection displays the returned result and plays particles around
  both the player and detector entity.
* Particle style may use returned `quality`, `elements`, and
  `variant_element`, but it must not reroll or infer the root.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Console runs `spirit-root-detector set` | Player-only message |
| Player runs `set` without looking at an entity | Target-missing message and `warn` log |
| Player runs `set` while looking at an entity | Config binding saved and `info` log records world/entity UUID |
| Admin runs `reload` | Config is re-read from disk and loaded count is reported |
| Player right-clicks unbound entity | Event is ignored |
| Player right-clicks bound detector without login cache | Fail closed with profile-not-loaded feedback |
| Game Service detection succeeds | Result message plus player/entity particle presentation |
| Game Service detection fails | Failure message; no particle success callback |

### 5. Good/Base/Bad Cases

* Good: entity listener delegates to a shared use case also used by the
  temporary command, so Game Service calls, logs, and failure behavior do not
  drift.
* Good: particle mapping is a presentation planner over the returned payload,
  not gameplay generation logic.
* Good: target selection uses entity bounding boxes or Paper ray tracing, so
  normal body/head aiming works for villagers and other non-point entities.
* Base: config contains only stable binding identity such as world and entity
  UUID.
* Bad: Adapter stores spirit-root quality, probability, or element-selection
  rules.
* Bad: detector bindings live only in a third-party plugin command chain with
  no reviewable ImmortalMC config.
* Bad: target selection compares the player's view direction only to
  `entity.getLocation()`; that point is often at the entity base, so looking at
  the visible body can falsely report "no target".

### 6. Tests Required

Java tests should assert:

* detector registry reloads, matches, saves, and deduplicates entity bindings
* admin commands reject console/missing target and save looked-at entity
* target selection can resolve a villager-height entity when the view ray
  crosses its body bounding box rather than its base point
* command parser resolves `spirit-root-detector set` and `reload`
* shared detection use case logs success/failure and only runs success callback
  after authoritative detection succeeds
* particle planner maps at least celestial, variant, dual/triple, and
  pseudo-root qualities to distinct visible styles
* resource tests cover `plugin.yml` usage and default detector config path

### 7. Wrong vs Correct

#### Wrong

```java
@EventHandler
public void onPlayerInteractEntity(PlayerInteractEntityEvent event) {
    SpiritRoot root = SpiritRootGenerator.roll();
    spawnParticles(event.getPlayer(), root);
}
```

This both invents the root in the Adapter and turns visual feedback into the
authoritative gameplay decision.

#### Correct

```java
detectionUseCase.detectForPlayer(
        player.getUniqueId(),
        "spirit_root_detector",
        player::sendMessage,
        result -> particlePresenter.play(player, detector, result.spiritRoot()));
```

The Adapter binds and presents the interaction; Game Service remains the
authority for the detected root.
