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

## Scenario: MythicMobs Combat Fact Ingestion

### 1. Scope / Trigger

Trigger: a Paper Adapter reports a MythicMobs death and Game Service credits
the current life's unrefined cultivation reserve.

### 2. Signatures

The Adapter sends `POST /api/v1/combat/mythicmob-kills/batch` with a versioned
batch of immutable facts. Each event includes `event_id`, `server_id`,
`entity_uuid`, exact `mob_internal_name`, decimal-string `mob_level`,
`killer_uuid`, optional `source_life_id`, `attribution_kind`, world/coordinates,
and timezone-aware `occurred_at`.

### 3. Contracts

Game Service owns the reward catalog and returns one result per event:
`accepted`, `duplicate`, `not_rewardable`, `account_not_found`, or
`current_life_unavailable`. Only `accepted` results contain reward and balance
fields. SQLite on the Adapter is a durable delivery outbox only; PostgreSQL is
the source of truth for kill facts, counters, ledger entries, and balances.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Unknown Mythic internal name | `not_rewardable`; no default amount |
| Missing/mismatched current life | `current_life_unavailable`; no historical credit |
| Same event and same request body | `duplicate` with the stored result |
| Same event with changed request body | conflict (`combat.kill_idempotency_conflict`) |
| Missing lethal ownership in Paper | Do not capture a reward event |

### 5. Good/Base/Bad Cases

* Good: native MythicMobs YAML uses `AzureWolf`; the versioned catalog maps the
  exact ID to a profile; a tracked lethal source produces one durable credit.
* Base: compact telemetry stores the immutable fact and materialized mob
  counter; boss entries opt into detailed policy.
* Bad: reading reward amounts from MythicMobs YAML, using `getKiller()` as an
  attribution fallback, or granting a local reward while Game Service is down.

### 6. Tests Required

* Catalog validation and level-boundary reward calculations.
* API acceptance, idempotent replay, changed-body conflict, unknown mob, and
  current-life mismatch.
* PostgreSQL transaction asserts exactly one kill fact, counter, ledger entry,
  and balance mutation.
* Paper startup with free MythicMobs 5.12.1 and artifact dependency isolation.

### 7. Wrong vs Correct

#### Wrong

```text
MythicMobs YAML -> local cultivation amount -> player balance
```

#### Correct

```text
MythicMobDeathEvent + tracked lethal owner
  -> SQLite durable fact outbox
  -> Game Service catalog/current-life validation
  -> PostgreSQL combat fact + cultivation ledger/balance
```

## Scenario: Mature Minecraft Plugin Ownership Boundaries

### 1. Scope / Trigger

Trigger: adding or integrating a third-party Paper plugin that overlaps with
NPCs, mobs, quests, combat, loot, or player progression.

### 2. Signatures

Approved runtime plugins and entry points:

* Citizens: `/npc` administration and the Citizens API for NPC identity,
  spawning, skins, names, navigation, and entity lifecycle.
* MythicMobs: `/mm` administration and the MythicMobs API/events for mob
  spawning, AI, mechanics, animation, and effects.
* ImmortalMC Adapter: Paper events and interaction actions that translate
  Minecraft-side facts to Game Service requests and present results.
* Game Service `quest` module: authoritative quest state, conditions,
  objectives, progression, and rewards.

Third-party quest engines are not the authoritative task system. The project
implements its own quest system through the Game Service and ImmortalMC
Adapter.

### 3. Contracts

* Citizens owns how an NPC exists in Minecraft. It must not own quest state,
  dialogue decisions, rewards, cultivation state, or account progression.
* Citizens integrations should persist the stable Citizens NPC ID when the API
  is available. A transient Bukkit entity UUID is not the long-term identity
  contract for a Citizens NPC.
* Citizens click deduplication and dialogue session state are separate
  contracts. A short event debounce may suppress duplicate click delivery, but
  only the dialogue/quest layer may decide whether an active or completed
  conversation can be started again.
* MythicMobs owns how a mob spawns, moves, targets, and presents skills. It may
  emit an attack or death fact, but it does not decide authoritative combat
  damage, loot eligibility, progression rewards, or cultivation outcomes.
* Game Service remains authoritative for quest, combat, loot, cultivation,
  reincarnation, and player progression data.
* Plugin-local YAML may configure presentation and mechanism details. Any state
  shared with another system must have an authoritative Game Service record.
* MMOCore is not an approved default dependency. Introducing it requires a
  separate design decision that identifies the exact engine capability being
  reused without adopting its class, mana, quest, or progression authority.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Citizens is absent | ImmortalMC core startup remains valid; Citizens-specific integration is disabled visibly |
| Citizens NPC respawns or server restarts | Business binding resolves by stable Citizens NPC ID, not a stale entity UUID |
| MythicMobs is absent | Non-Mythic ImmortalMC behavior remains valid; Mythic integration is disabled visibly |
| Mythic mob attacks or dies | Adapter reports facts; Game Service calculates trusted results |
| Plugin API/version is incompatible | Test server startup fails visibly; do not suppress the error or silently downgrade behavior |
| Authoritative Game Service data is unavailable | Do not substitute plugin-local progression, damage, or reward values |

### 5. Good/Base/Bad Cases

* Good: Citizens creates a named, skinned NPC; ImmortalMC binds it to a custom
  quest/dialogue action; Game Service owns the player's quest state.
* Base: MythicMobs creates and animates a configured monster while ImmortalMC
  only observes Minecraft events until an authoritative gameplay slice is
  connected.
* Bad: a Citizens trait or third-party quest plugin becomes the only record of
  quest completion and rewards.
* Bad: MythicMobs configuration directly grants authoritative cultivation
  resources without Game Service validation.

### 6. Tests Required

* Test-server boot must prove Citizens, MythicMobs, and ImmortalMC enable
  without severe errors on the pinned Paper and Java versions.
* The local pinned BetterHud `2.0.0` artifact requires a Java 25 runtime
  (class-file version 69); `scripts/start-paper-server.sh` must prefer Java 25
  or the server will disable BetterHud before ImmortalMC starts.
* Citizens integration must test that an NPC binding survives a server restart
  and resolves after the backing Bukkit entity is recreated.
* MythicMobs integration must test that reported combat/kill facts cannot inject
  trusted damage, loot, or reward values into Game Service.
* Quest slices must test state transitions and reward idempotency in Game
  Service independently of Citizens or MythicMobs availability.

### 7. Wrong vs Correct

#### Wrong

```text
MythicMobs kill mechanic -> directly grant cultivation reward
Citizens/quest-plugin YAML -> only source of quest completion state
```

#### Correct

```text
Citizens NPC interaction -> ImmortalMC Adapter -> Game Service quest command
MythicMobs combat/death fact -> ImmortalMC Adapter -> Game Service calculation
Game Service result -> ImmortalMC presentation/reward delivery
```

## Scenario: Citizens Quest Provider Authoring

### 1. Scope / Trigger

Trigger: an operator needs to attach an existing authoritative Game Service
quest-provider template to a physical Citizens NPC without copying entity or
Citizens UUIDs into YAML.

### 2. Signatures

Game Service catalog API:

```http
GET /api/v1/quest-providers
```

Minecraft authoring commands:

```text
/npc select <id|name>
/immortal quest templates
/immortal quest bind <provider-id>
/immortal quest info
/immortal quest list
/immortal quest unbind
/immortal quest reload
```

Citizens selection API:

```java
CitizensAPI.getDefaultNPCSelector().getSelected(commandSender)
```

### 3. Contracts

The catalog response is typed and versioned:

```json
{
  "contract_version": 1,
  "revision": "sha256:...",
  "providers": [
    {
      "provider_id": "old-man",
      "display_name": "老村民",
      "main_quest_ids": ["first-steps"],
      "side_quest_ids": []
    }
  ]
}
```

Game Service is the only provider-template source. The Adapter caches the last
confirmed catalog only for command validation, listing, and tab completion; it
must not mirror provider IDs in Paper configuration.

Binding writes one normal `quest-provider` interaction with:

```yaml
target-provider: citizens
citizens-npc-uuid: <Citizens persistent UUID>
quest-provider-id: <validated provider ID>
citizens-npc-id: <current numeric Citizens ID>
citizens-npc-name: <current display name>
```

The persistent Citizens UUID is the routing identity. The Bukkit entity UUID
and world in the interaction record are presentation fallbacks and may change
after respawn. Each Citizens NPC has at most one quest-provider binding; one
provider template may be reused by many Citizens NPCs. Rebind replaces only the
selected NPC's old quest-provider binding. Unbind never deletes or despawns the
Citizens NPC.

HTTP catalog refresh runs asynchronously. Catalog confirmation, Bukkit/Citizens
access, configuration writes, tab completion, and command messages stay on the
Paper main thread.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| No player Citizens selection | Reject and instruct `/npc select <id|name>`; never fall back to look-at targeting |
| Selected NPC is not spawned during bind | Reject without changing the previous binding |
| No confirmed catalog | Bind fails closed; no interaction is written |
| Unknown provider ID | Reject before removing or writing a binding |
| Catalog refresh fails after an earlier success | Preserve the previous confirmed catalog and all bindings |
| Rebind selected NPC | Remove that NPC's old quest-provider binding, then write the validated replacement |
| Same provider bound to another NPC | Allow it; provider templates are reusable content |
| Citizens NPC respawns or Paper restarts | Resolve click/proximity behavior by persistent Citizens UUID |
| Unbind selected NPC | Remove ImmortalMC metadata only; keep the Citizens NPC intact |

### 5. Good/Base/Bad Cases

* Good: select NPC `1`, bind `old-man`, restart Paper, select NPC `1` again,
  and `quest info` resolves the same binding by persistent Citizens UUID.
* Base: `quest templates` lists provider IDs/display names and `quest bind`
  confirms the selected NPC name, numeric ID, provider ID, and display name.
* Bad: require an operator to paste a Bukkit entity UUID or Citizens UUID.
* Bad: keep a duplicate provider list in `config.yml` and accept bindings while
  Game Service has no confirmed definition for that ID.
* Bad: use an implicit look-at fallback when no Citizens selection exists.

### 6. Tests Required

* Game Service integration test asserts the exact catalog response, provider
  order, ordered main/side quest IDs, and definition revision.
* Java HTTP-client test asserts `GET`, snake-case decoding, contract version,
  and ordered quest lists.
* Cache tests assert only the last confirmed catalog is exposed and a failed
  refresh cannot erase it.
* Command tests cover exact parser signatures and provider-ID tab completion.
* Admin-runner tests cover player/selection/spawn validation, unknown provider
  fail-closed behavior, rebind replacement, provider reuse across NPCs,
  unbind-without-delete behavior, and persisted UUID metadata after reload.
* Local Paper smoke test selects a real Citizens NPC, exercises
  `info/bind/unbind/bind`, clicks into the quest flow, restarts Paper, and
  verifies `info` still resolves the binding.

### 7. Wrong vs Correct

#### Wrong

```text
/immortal quest bind old-man <copied-entity-uuid>
Paper config provider-ids: [old-man]
Game Service outage -> accept unchecked binding
```

#### Correct

```text
/npc select 1
/immortal quest bind old-man
Citizens selection -> persistent NPC UUID -> validated cached catalog -> binding
Catalog refresh failure -> preserve last confirmed catalog and existing binding
```

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
* If public behavior changed, was the relevant `docs/wiki/` page updated and
  linked, and did `python3 scripts/check-wiki-links.py` pass?

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

## Scenario: Authoritative Quest NPC Presentation

### 1. Scope / Trigger

Trigger: Paper presents Game Service quest state through Citizens proximity,
dialogue sessions, private labels, titles, particles, or scoreboards.

### 2. Signatures

```http
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
PUT /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
```

Mutation requests require `Idempotency-Key: <UUID>` and JSON
`{"provider_id":"<quest-provider-id>"}`. Paper refreshes through a
`CompletableFuture<QuestInteractionState>` whose published completion runs on
the Bukkit main thread.

### 3. Contracts

* Game Service owns quest state, objective evaluation, revisions, and mutation
  idempotency. Paper owns only short-lived presentation state.
* A Citizens quest NPC is identified by persistent NPC UUID plus stable
  `quest-provider-id`; transient Bukkit entity UUIDs are not quest identity.
* Proximity scanning runs from an indexed, bounded coordinator. Cache misses
  use the shared single-flight refresh path and never block the server thread.
* Record the current inside-NPC set before starting enter callbacks. A supplied
  future may already be complete and execute its completion inline.
* A refresh completion may speak only when its life ID matches the entering
  life, the player is still inside that NPC, and the response still contains
  the provider and bark.
* `proximity_bark` includes non-empty `speaker` and `text` fields. Format them
  through the same shared speaker-line helper used by formal NPC dialogue.
* Offer sessions are cancelled when the player leaves range/world, disappears,
  expires, or the persistent Citizens NPC disappears from the current index.
* Private offer-label Y position is backing-entity `getHeight()` plus nameplate
  clearance. Sidebar objectives use `NumberFormat.blank()` to hide order scores.
* Accept/turn-in retries are owned by the request coordinator. Retry at most
  once for I/O failures or `GameServiceException.retryable() == true`, using the
  same request closure and therefore the same operation UUID.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Fresh provider cache | Send at most one private bark on the outside-to-inside edge; no HTTP |
| Missing/stale cache | Start or join one refresh; speak on completion only if context remains valid |
| Player leaves before refresh completes | Drop the bark without changing cooldown state |
| Response life differs | Drop the response as stale |
| Provider/bark absent from response | Send nothing; do not invent fallback quest text |
| Bark speaker missing/invalid | Reject the Adapter DTO instead of showing unattributed dialogue |
| Citizens NPC disappears | Cancel its pending offer label/session on the next shared scan |
| Retryable mutation transport failure | Retry once with the same `Idempotency-Key` |
| Non-retryable/domain mutation failure | Do not retry; preserve confirmed cosmetic state |
| Game Service mutation fails | Keep authoritative quest/sidebar state unchanged and show retry feedback |

### 5. Good/Base/Bad Cases

* Good: cache miss -> coalesced async refresh -> main-thread context validation
  -> private bark through the same state-key cooldown path as cache hits.
* Base: a 10-tick scan checks only current/adjacent chunks and carries excess
  players to a later scan.
* Bad: send a bark directly from an HTTP completion thread or after the player
  has left the NPC.
* Bad: keep a pending private label after the Citizens NPC despawns.

### 6. Tests Required

* A completed refresh future speaks immediately when the player is still in
  range. This specifically proves inside state is committed before callbacks.
* Client decoding preserves bark `speaker`; coordinator output includes the
  colored speaker prefix and formal dialogue formatting remains unchanged.
* Bukkit boundary tests assert blank sidebar number format and label placement
  at runtime entity height plus clearance.
* Cache-hit entry performs zero HTTP and remaining inside does not repeat bark.
* State-key changes bypass an old bark cooldown; unchanged state does not.
* Range, world, timeout, missing player, and missing NPC each remove an offer
  label exactly once.
* A 100-player/25-NPC fixture asserts bounded candidates and scan carryover.
* A retryable mutation failure causes exactly two gateway calls carrying the
  same operation UUID; a non-retryable domain failure causes exactly one.
* Full Game Service tests and a clean Paper build pass before deployment; the
  runtime log must contain no `SEVERE`, `ERROR`, or unexpected exception.

### 7. Wrong vs Correct

#### Wrong

```java
refresher.refresh(...).thenAccept(state -> barkSink.send(playerId, bark(state)));
insideNpcIdsByPlayer.put(playerId, current);
```

An already-completed future runs inline before the player is recorded inside,
and an incomplete future can speak after the context becomes stale.

#### Correct

```java
insideNpcIdsByPlayer.put(playerId, current);
refresher.refresh(...).whenComplete((state, error) -> {
    if (error == null && sameLife(state) && isStillInside(playerId, npcId)) {
        sendThroughStateCooldown(state);
    }
});
```

Commit scan state first, then validate every asynchronous completion before
touching player-visible presentation.

## Scenario: Cultivation Projection Across Game Service and Paper

### 1. Scope / Trigger

Trigger: a cultivation field, combat reward result, seclusion/breakthrough DTO,
HUD placeholder, XP-orb presentation, or cultivation GUI flow changes.

### 2. Signatures

```http
GET  /api/v1/players/{account_id}/current-life/cultivation
GET  /api/v1/players/{account_id}/current-life/cultivation/techniques
POST /api/v1/players/{account_id}/current-life/cultivation/seclusions
POST /api/v1/players/{account_id}/current-life/cultivation/breakthroughs
POST /api/v1/players/{account_id}/current-life/items/adjustments
```

Paper consumes snake-case JSON through typed Jackson records and sends UUID
`Idempotency-Key` headers for mutations.

The learned-technique response includes `attribute_codes: string[]`; Paper
renders it as presentation metadata and never interprets it as combat logic.
Player commands are `/immortal seclusion` and
`/immortal breakthrough <pill-count>` under `immortalmc.cultivation`.
Administrative commands remain under `immortalmc.command`.

### 3. Contracts

* Game Service owns reward amounts, reserve caps, cultivation math, area
  modifiers, technique eligibility, breakthrough rolls, penalties, and storage.
* Paper reports facts/IDs and presents results. It never sends trusted reward,
  speed, yield, success, penalty, or cultivation amounts.
* Only `accepted` combat results create visual XP orbs. `duplicate` and terminal
  no-reward results are acknowledged without presentation.
* Visual orbs have zero vanilla XP, are owner-tagged, cannot merge, and only the
  owner pickup triggers a HUD refresh. Orb count depends only on mob level.
* HUD state is keyed by player plus current life. Old-life asynchronous
  responses cannot overwrite a new life even with a higher revision.
* BetterHud/resource-pack absence disables presentation with a visible warning
  and never changes gameplay or outbox acknowledgement.
* Paper cultivation-area cuboids resolve only a stable semantic `area-id`.
  The submitted ID must exist in the Game Service area catalog; Paper never
  submits speed/yield values.
* A seclusion settlement response with `status=active` is a partial
  authoritative settlement. Paper refreshes the HUD and schedules another
  settlement; only `completed` is presented as closed.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Accepted reward credited amount is zero because reserve is full | Present accepted visual feedback; authoritative amount remains zero |
| Duplicate delivery | No second orb/HUD animation |
| Owner is offline | No orb; reconnect fetches authoritative snapshot |
| Old-life response arrives late | Drop it |
| BetterHud is absent or reload fails | Warn and keep gameplay active |
| Reserve cap is zero | Render ratio without divide-by-zero or NaN |
| GUI submits mixed major realms | Paper blocks preflight; Game Service still rejects manipulated requests |
| Duplicate/unknown/ineligible technique or unknown area | Structured `cultivation.seclusion_rule_violation` conflict; no session |
| Existing session or reused key with different request | Structured `cultivation.seclusion_conflict`; no second mutation |
| Unknown, wrong-life, or wrong-kind seclusion session | Structured `cultivation.seclusion_not_found` |
| Settlement has no new elapsed/generated cultivation | Structured `cultivation.seclusion_conflict` |
| Breakthrough item quantity is insufficient | Structured `item.insufficient_quantity`; item/session/debits roll back |
| Paper settlement returns `active` | Do not announce completion; refresh and schedule another settlement |

### 5. Good/Base/Bad Cases

* Good: outbox response -> accepted-only main-thread presentation -> independent
  acknowledgement -> authoritative snapshot refresh.
* Base: BetterHud placeholders read a last-confirmed immutable projection.
* Bad: derive cultivation reward from orb count or Minecraft XP state.
* Bad: trust GUI eligibility/rates without Game Service validation.

### 6. Tests Required

* Jackson and Pydantic field names round-trip for every cultivation DTO.
* Outbox tests cover accepted, duplicate, presenter failure, and dispatcher
  failure while terminal acknowledgement still occurs.
* Orb tests cover zero XP, ownership, wrong-player pickup, and merge prevention.
* Projection tests cover revision monotonicity and life replacement races.
* Resource tests assert BetterHud YAML, text font, alpha PNG dimensions, and
  soft dependency.
* Technique DTO tests assert `attribute_codes`, display name, layer, status,
  and snake-case/camel-case mapping.
* Command/resource tests assert public cultivation permission, retained admin
  permission, and a default area ID present in the Game Service catalog.
* Settlement tests assert tick rounding never fires before `completes_at` and
  `active` causes another scheduled attempt.
* API tests assert all expected seclusion/breakthrough rule, conflict,
  not-found, and item-shortage paths return stable error envelopes rather than
  HTTP 500.
* Full Gradle `test build` passes with BetterHud absent from the test runtime.

### 7. Wrong vs Correct

#### Wrong

```java
long reward = mobLevel * 10;
player.giveExp((int) reward);
```

#### Correct

```java
if (result.outcome().equals("accepted")) {
    presenter.present(killFact, result); // zero-XP visual only
}
client.fetchCultivation(accountId).thenAccept(this::publishOnMainThread);
```

The Adapter visualizes authoritative results and refreshes projections; it does
not become a second progression engine.

## Scenario: Typed Quest Objectives and Cross-Layer Projection

### 1. Scope / Trigger

Trigger: a quest needs item delivery, MythicMobs kill counts, a specified
technique layer, or a specified realm level, and the result is shown through a
Citizens/Paper tracked-quest sidebar.

### 2. Signatures

Backend definitions and persistence:

```text
ItemDeliveryObjectiveDefinition(item_code, required_quantity)
MythicMobKillObjectiveDefinition(mob_internal_name, required_count)
TechniqueLayerObjectiveDefinition(technique_id, target_layer)
RealmLevelObjectiveDefinition(target_level)
quest_objective_progress(life_id, quest_id, objective_id, definition_version,
                          objective_type, target_id, required_value,
                          current_value, updated_at)
```

Adapter endpoints and refresh:

```http
POST /api/v1/players/{account_id}/current-life/quest-interaction-state
PUT  /api/v1/players/{account_id}/current-life/quests/{quest_id}/accept
PUT  /api/v1/players/{account_id}/current-life/quests/{quest_id}/turn-in
```

`TrackedQuestRefreshCoordinator.refresh(playerUuid)` calls the state endpoint
with an empty provider list. `publish` accepts a complete mutation response;
both paths publish only on the Paper main thread.

### 3. Contracts

* A quest has one to twelve objectives. All objectives use AND semantics.
* Application composition validates every MythicMob, technique/layer, and
  realm objective against the exact shared authoritative catalogs before the
  service starts. Quest/provider relationships are non-empty and bidirectionally
  consistent. Item targets remain stable IDs until a complete item catalog exists.
* Item, technique, and realm objectives read current authoritative state at
  acceptance, projection, and turn-in. Technique reads the active specified
  `LifeTechnique.current_layer`; realm uses `current_level`.
* A rewardable combat fact must include the life observed by the Adapter. A
  missing or stale `source_life_id` is terminal `current_life_unavailable`, so
  delayed outbox delivery cannot attach an old kill to a newly reincarnated
  life.
* Kill rows start at zero on acceptance and advance only for a newly inserted
  authoritative kill with matching exact mob ID and `occurred_at >= accepted_at`.
  Historical lifetime counters are not a quest baseline. Progression locks the
  per-life quest revision before reading accepted state, so an accept/kill race
  cannot commit the combat event while dropping its objective increment.
* Cultivation writes `invested_amount` and `current_layer` together through
  the shared layer curve. Migration `20260718_003` backfills existing rows
  before services trust direct layer reads.
* Turn-in acquires sorted transaction advisory locks for item operation keys,
  then locks all distinct delivery stacks in sorted item-code order, validates
  every replay identity and balance, consumes all items, and completes the
  quest in one transaction. Reusing an item operation UUID with different life,
  quantity, type, or session is a conflict; it must never leak an
  `IntegrityError`, look like a replay, or leave an earlier item partially debited.
  The completion update must affect exactly one active row after the debit; an
  impossible false result aborts the Unit of Work.
* Migration `20260718_003` uses a frozen copy of the authored cultivation curve
  for legacy layer backfill so later balance changes cannot rewrite history.
* The response keeps `current/required/completed` unchanged for all objective
  types. `revision.objectives` advances with cultivation and item-stack
  dependencies; Paper rejects component-wise older vectors.
* Paper renders at most twelve objective rows plus title and hint, and does
  not calculate or submit progress values.
* Join-login and tracked-quest refresh attempts use non-reusable monotonic
  tokens. Quit/kick/disable invalidates them, and a completion must still match
  the active online join plus account/life before it may cache or render.

### 4. Validation & Error Matrix

| Condition | Expected behavior |
|---|---|
| Non-positive quantity/count/layer/level, invalid provider relation, or unknown catalog target | Application startup fails visibly |
| Kill races with quest acceptance | Wait for acceptance commit, then count exactly once |
| Kill before acceptance, wrong mob, wrong life, or duplicate event | No quest counter increment |
| Missing `source_life_id` on a rewardable kill | `current_life_unavailable`; no counter or reward |
| Active technique abandoned or technique/realm regresses | Projection returns `active` again |
| Any delivery stack is short | `quest.not_ready`; no item debit or completion |
| Item operation UUID reused with different immutable facts | `quest.idempotency_conflict` (or cultivation conflict); no mutation |
| Concurrent operation UUID collision | Advisory-lock loser reloads the winner and returns a stable replay/conflict |
| Older asynchronous account/life/revision response | Drop it without rendering |
| Player quits and rejoins the same life before an old response completes | Non-reusable token drops the old completion |
| More than twelve objectives | Catalog validation rejects the quest |

### 5. Good/Base/Bad Cases

* Good: combat event insertion, quest counter update, reward credit, and
  lifetime counter commit in one Unit of Work; Paper refreshes after accepted
  or duplicate delivery.
* Base: current state objectives are batch-loaded for projection and the
  tracked refresh is coalesced with one trailing request when dirty.
* Bad: derive kill progress from a lifetime counter, trust a Paper-submitted
  count/layer, or consume the first item before validating the second.

### 6. Tests Required

* Definition tests assert each type's boundaries, duplicate targets, and the
  twelve-objective catalog limit.
* PostgreSQL tests assert acceptance timestamps, bounded batch counter updates,
  duplicate kill idempotency, atomic multi-item shortage, cross-domain item
  UUID conflicts (including a later-item conflict), migration metadata and
  legacy backfill, missing-source-life rejection, and current-layer gain/loss
  persistence.
* Concurrency tests hold acceptance and item-operation locks open, assert the
  competing transaction actually waits, then prove exact progress and stable
  replay/conflict behavior after the winner commits.
* Service tests assert mixed-objective AND behavior, current-state credit,
  regression after readiness, completed projection freezing, and new-life
  isolation.
* Java tests assert coalescing, trailing refresh, stale-life/revision drops,
  clear-and-same-life reconnect ABA protection, late-login invalidation,
  dispatcher recovery, multi-row scoreboard rendering, and accepted/duplicate
  outbox refresh deduplication.

### 7. Wrong vs Correct

#### Wrong

```text
quest turn-in -> consume item A -> discover item B is short -> return failure
```

#### Correct

```text
lock all sorted stacks -> validate every balance -> consume all -> complete
```

The authoritative transaction, not the Paper projection, decides whether the
quest can complete.
