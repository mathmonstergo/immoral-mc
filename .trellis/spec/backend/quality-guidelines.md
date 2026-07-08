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
