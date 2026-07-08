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
