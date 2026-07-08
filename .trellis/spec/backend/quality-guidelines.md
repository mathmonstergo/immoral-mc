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

## Server Development Design Principles

Apply these constraints to Game Service and Paper Adapter work:

* Make small, precise changes and avoid unrelated refactors.
* Find the business invariant and express it in one place.
* When shared validation, configuration, permissions, caching, or API contracts change, prefer one unified entry point.
* Do not use broad `try/catch` blocks to swallow errors.
* Do not use silent fallbacks to hide problems.

Logic encapsulation rules:

* Avoid fragmentation: do not split code merely for the sake of splitting.
* Avoid over-design: do not break a complete business flow into many one-off tiny private methods.
* Prefer readability: the main business flow should remain understandable in the current method where practical.
* Extract an abstraction only when it has real reuse, reduces complexity, or the method is clearly too long.

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

## Scenario: Paper Adapter Entity Interaction Actions

### 1. Scope / Trigger

Trigger: Paper Adapter turns command-driven gameplay tests into Wynncraft-style
in-world interactions bound to server-authored entities. Spirit-root detection
is the first action on this generic entity-interaction foundation; later NPC
dialogue, shops, quests, and other entity interactions must reuse the same
binding/protection/routing layer.

### 2. Signatures

Generic infrastructure:

* Paper event: `PlayerInteractEntityEvent`
* Registry: `EntityInteractionRegistry`
* Config path: `content.entity-interactions.entries`
* Action router:
  `EntityInteractionActionRouter<BukkitEntityInteractionContext>`

Spirit-root authoring wrapper:

* Minecraft admin command: `/immortal spirit-root-detector create`
* Minecraft admin command: `/immortal spirit-root-detector list`
* Minecraft admin command: `/immortal spirit-root-detector remove`
* Minecraft player command: `/immortal spirit-root-detector set`
* Minecraft admin command: `/immortal spirit-root-detector reload`

Config entry fields:

* `id`: stable interaction ID, e.g. `spirit-root-detect-1`
* `action`: action key, e.g. `spirit-root-detect`, `npc-dialogue`
* `world`: Bukkit world name
* `entity-uuid`: bound entity UUID
* `entity-type`: Bukkit entity type name
* `protected`: whether protection listeners protect this entity
* `managed-entity`: whether ImmortalMC owns the underlying entity and should
  delete it when the interaction is removed

Legacy migration:

* Old `content.spirit-root.detectors` entries containing only `world` and
  `entity-uuid` must load as `spirit-root-detect` interactions when the new
  path is not explicitly set in the disk config. They default to
  `managed-entity: false`.

Spirit-root action:

* Shared use case:
  `SpiritRootDetectionUseCase.detectForPlayer(UUID minecraftUuid, String logEventPrefix, Consumer<String> sendMessage, Consumer<SpiritRootDetectionResult> onSuccess)`
* Presentation planner:
  `SpiritRootParticlePlanner.plan(SpiritRootSnapshot root)`

### 3. Contracts

Generic interaction contract:

* Entity binding and protection are generic; do not name the generic layer
  "detector" or hardcode spirit-root behavior there.
* Right-clicking a configured entity looks up all interactions for that
  `world + entity-uuid`, then routes by `action`.
* Unknown actions are logged as warnings and do not invent gameplay behavior.
* Protected interactions cancel common entity disruption events such as damage,
  death, combustion, movement, teleport, transform, and targeting.

Spirit-root detector authoring:

* `create` requires an in-game player sender, spawns a persistent protected
  entity, and saves it as action `spirit-root-detect` with
  `managed-entity: true`.
* `list` shows only interactions with action `spirit-root-detect`.
* `remove` removes only the looked-at entity's `spirit-root-detect`
  interaction. If the interaction has `managed-entity: true`, it also deletes
  the underlying entity. If it has `managed-entity: false`, it only unbinds
  and must not delete arbitrary existing entities.
* `set` requires an in-game player sender.
* `set` saves the entity the player is looking at as action
  `spirit-root-detect` with `managed-entity: false`, not a block coordinate.
* `reload` reloads interaction bindings from disk-backed config.
* Saved interaction bindings remain reviewable as config data.

Spirit-root detector interaction:

* Only right-clicking an entity with action `spirit-root-detect` triggers
  detection.
* The Adapter resolves the player through `PlayerSessionCache` and calls Game
  Service with only the authoritative `account_id`.
* Successful detection displays the returned result and plays particles around
  both the player and detector entity.
* Particle style may use returned `quality`, `elements`, and
  `variant_element`, but it must not reroll or infer the root.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Disk config has only legacy `content.spirit-root.detectors` and default config has new empty path | Legacy detector entries still load as `spirit-root-detect` interactions |
| Disk config explicitly has `content.entity-interactions.entries` | New generic path takes precedence over legacy detector path |
| Console runs `spirit-root-detector create`, `set`, or `remove` | Player-only message |
| Player runs `create` | Protected persistent entity is spawned and saved as action `spirit-root-detect` with `managed-entity: true` |
| Player runs `set` without looking at an entity | Target-missing message and `warn` log |
| Player runs `set` while looking at an entity | Interaction saved with `managed-entity: false`; `info` log records ID/action/world/entity UUID |
| Player runs `remove` on a managed detector | Interaction is removed from config and the entity is deleted from the world |
| Player runs `remove` on an unmanaged detector | Interaction is removed from config and the entity remains in the world |
| Player runs `remove` on a managed detector whose entity is already missing | Interaction is removed; `warn` log records missing entity |
| Player runs `remove` while looking at an unbound entity | Not-bound message and `warn` log |
| Admin runs `list` | Current `spirit-root-detect` interactions are listed |
| Admin runs `reload` | Config is re-read from disk and loaded count is reported |
| Player right-clicks unbound entity | Event is ignored |
| Player right-clicks entity with unknown action | Warning log; no gameplay fallback |
| Player right-clicks `spirit-root-detect` without login cache | Fail closed with profile-not-loaded feedback |
| Game Service detection succeeds | Result message plus player/entity particle presentation |
| Game Service detection fails | Failure message; no particle success callback |

### 5. Good/Base/Bad Cases

* Good: entity binding, action routing, and protection are generic, while
  spirit-root detection is registered as one action handler.
* Good: the spirit-root action delegates to the shared detection use case also
  used by the temporary command, so Game Service calls, logs, and failure
  behavior do not drift.
* Good: particle mapping is a presentation planner over the returned payload,
  not gameplay generation logic.
* Good: target selection uses entity bounding boxes or Paper ray tracing, so
  normal body/head aiming works for villagers and other non-point entities.
* Base: config contains stable interaction identity and binding fields:
  `id`, `action`, `world`, `entity-uuid`, `entity-type`, `protected`,
  `managed-entity`.
* Bad: creating a second hardcoded listener/registry for NPC dialogue or
  another entity interaction instead of adding an action handler.
* Bad: Adapter stores spirit-root quality, probability, or element-selection
  rules.
* Bad: detector bindings live only in a third-party plugin command chain with
  no reviewable ImmortalMC config.
* Bad: target selection compares the player's view direction only to
  `entity.getLocation()`; that point is often at the entity base, so looking at
  the visible body can falsely report "no target".

### 6. Tests Required

Java tests should assert:

* entity interaction registry reloads, action-filters, matches, saves,
  deduplicates, and removes entity bindings
* config mapper migrates legacy detector entries even when defaults contain
  the new empty path, and defaults missing `managed-entity` to false
* action router dispatches registered actions and rejects unknown actions
* admin commands reject console/missing target and create/list/remove/set
  spirit-root detector interactions
* removing a managed detector deletes the underlying entity through the Paper
  adapter; removing an unmanaged detector only unbinds it
* target selection can resolve a villager-height entity when the view ray
  crosses its body bounding box rather than its base point
* command parser resolves `spirit-root-detector create`, `list`, `remove`,
  `set`, and `reload`
* shared detection use case logs success/failure and only runs success callback
  after authoritative detection succeeds
* particle planner maps at least celestial, variant, dual/triple, and
  pseudo-root qualities to distinct visible styles
* resource tests cover `plugin.yml` usage and default generic interaction
  config path

### 7. Wrong vs Correct

#### Wrong

```java
@EventHandler
public void onPlayerInteractEntity(PlayerInteractEntityEvent event) {
    if (isDialogueNpc(event.getRightClicked())) {
        openDialogue(event.getPlayer());
        return;
    }
    if (isSpiritRootDetector(event.getRightClicked())) {
        SpiritRoot root = SpiritRootGenerator.roll();
        spawnParticles(event.getPlayer(), root);
    }
}
```

This fragments entity interactions into hardcoded branches and invents the
spirit-root result in the Adapter.

#### Correct

```java
registry.findAll(binding).forEach(definition -> router.route(
        definition,
        new BukkitEntityInteractionContext(player, entity)));
```

The Adapter has one entity-interaction entry point. Each action handler owns
only its presentation/adapter behavior, and Game Service remains the authority
for progression-defining results.

## Scenario: Paper Adapter NPC Dialogue Interaction

### 1. Scope / Trigger

Trigger: add the second concrete entity interaction action, `npc-dialogue`, to
prove NPCs, quests, shops, and scripted interactions can reuse the generic
entity interaction layer.

### 2. Signatures

* Minecraft admin command: `/immortal npc-dialogue set <dialogue-id>`
* Minecraft admin command: `/immortal npc-dialogue list`
* Minecraft admin command: `/immortal npc-dialogue remove`
* Minecraft admin command: `/immortal npc-dialogue reload`
* Entity interaction action key: `npc-dialogue`
* Interaction metadata key: `dialogue-id`
* Dialogue content path: `plugins/ImmortalMC/dialogues/<dialogue-id>.yml`

### 3. Contracts

`npc-dialogue` interaction entries are normal
`content.entity-interactions.entries` items with:

```yaml
id: "npc-dialogue-1"
action: "npc-dialogue"
world: "world"
entity-uuid: "00000000-0000-0000-0000-000000000000"
entity-type: "VILLAGER"
protected: true
managed-entity: false
dialogue-id: "old-man"
```

Dialogue YAML file shape:

```yaml
id: old-man
title: "初入凡尘"
speaker: "老村民"
line-delay-ticks: 30
sound: "entity.villager.ambient"
pitch: 1.0
opening-lines:
  - "§6§l任务开始"
  - "§e初入凡尘"
lines:
  - "年轻人，你身上有一股未定的气。"
```

Rules:

* `set` binds the looked-at entity to an already-loaded dialogue id.
* `set` always writes `managed-entity: false`; external plugins may own the
  NPC entity.
* Right-clicking the bound entity sends a fixed-height stylized opening block,
  then schedules NPC lines every `line-delay-ticks`.
* Each NPC line plays the configured sound with slight pitch variation around
  `pitch`.
* Optional YAML fields use defaults only when omitted; if an optional field is
  present with the wrong type, loading must fail instead of silently defaulting.
* Dialogue presentation is intentional player UX; operational traces use Paper
  logs.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Console runs `npc-dialogue set` or `remove` | Player-only message |
| Player runs `set` without looking at an entity | Target-missing message and `warn` log |
| Player runs `set <missing-id>` | No binding saved; message points to `dialogues/<id>.yml`; `warn` log |
| Player runs `set <loaded-id>` | Binding saved as action `npc-dialogue` with `dialogue-id` metadata and `managed-entity: false` |
| Player right-clicks a bound NPC with loaded content | Opening block appears, then delayed lines with sound |
| Bound interaction has no `dialogue-id` metadata | `warn` log; no fallback dialogue |
| Bound interaction references missing content | `warn` log; no fallback dialogue |
| Dialogue YAML has a malformed optional field type | Dialogue loading fails visibly; no silent default is applied |
| Admin runs `reload` | Entity bindings and dialogue YAML files are reloaded |

### 5. Good/Base/Bad Cases

* Good: NPC dialogue is a registered `EntityInteractionAction`, not a second
  entity listener.
* Good: entity binding and dialogue content are separated; multiple NPCs can
  point at the same `dialogue-id`.
* Good: dialogue content is data-driven YAML and reviewable in version control.
* Base: `dialogue-id` is interaction metadata, so future actions can add their
  own metadata keys without changing the base registry again.
* Bad: hardcoding NPC text in Java.
* Bad: deleting the NPC entity on `npc-dialogue remove`; the entity may belong
  to another plugin.
* Bad: silently showing placeholder dialogue when YAML content is missing.

### 6. Tests Required

Java tests should assert:

* config mapper reads/writes interaction metadata such as `dialogue-id`
* `/immortal npc-dialogue set <dialogue-id>` saves action `npc-dialogue` with
  `managed-entity: false`
* list/remove/reload operate only on `npc-dialogue` bindings
* YAML repository loads `dialogues/<id>.yml` and applies defaults
* YAML repository rejects malformed optional field types instead of applying
  defaults
* presenter sends the opening block immediately, schedules lines by ticks, and
  plays sound with pitch variation
* action handler logs and sends no fallback content when metadata/content is
  missing
* plugin resources include an example dialogue file and command usage

### 7. Wrong vs Correct

#### Wrong

```java
if (entity.getName().equals("old-man")) {
    player.sendMessage("年轻人，你身上有一股未定的气。");
}
```

This hardcodes content, bypasses reloadable YAML, and ties behavior to an entity
name instead of the generic interaction registry.

#### Correct

```java
definition.metadataValue("dialogue-id")
        .flatMap(dialogueRegistry::find)
        .ifPresent(dialogue -> presenter.play(dialogue, audience));
```

The binding decides which content id to use, the YAML registry owns dialogue
content, and the action handler owns only presentation behavior.
