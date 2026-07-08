# Player Account and Spirit Root Slice

## Goal

Create the first gameplay-facing Game Service slice: an Adapter-facing API that can register or look up a Minecraft player account, create the current first-life character record, and perform spirit root detection for that life.

This is the first step toward the documented vertical slice:

```text
enter game -> spirit root check -> join sect -> learn technique -> kill monster -> gain resource -> breakthrough -> save data
```

## What I Already Know

* `architecture-v2.md` establishes Game Service as the authoritative MMORPG rules backend.
* Paper Adapter should report Minecraft facts and call Game Service; it should not decide progression outcomes.
* `game-design-reincarnation-inheritance.md` says the player model must eventually split permanent `Account` from per-generation `Life`.
* The same document says Phase 1 should first run "one account = one life" before introducing full reincarnation.
* Current `game-service/` is a working FastAPI scaffold with `/health`, `/docs`, pytest, and Ruff.
* The project has no database integration yet.

## Requirements

* Add a `player` module API under the existing FastAPI app.
* Add an Adapter-facing endpoint to get or create an account and its current life from Minecraft identity.
* Add an endpoint to detect the current life spirit root.
* Preserve the account/life split in data structures even though this MVP only creates generation 1.
* Spirit root detection must be owned by Game Service, not supplied by the client or future Paper Adapter.
* Spirit root result must include quality and element composition, not a single flat element string.
* Repeated spirit root detection for the same current life should return the existing result, not reroll.
* Use an in-memory repository for this task only, behind a service/repository boundary that can later be replaced with PostgreSQL.
* Include tests for account creation, idempotent lookup, first-life creation, spirit root detection, and detection idempotency.
* Keep the API shape stable enough for a future Paper Adapter to call.

## Acceptance Criteria

* [x] `POST /api/v1/players/login` accepts Minecraft player identity and returns account plus current life.
* [x] Repeating `POST /api/v1/players/login` with the same Minecraft UUID returns the same account/current life.
* [x] `POST /api/v1/players/{account_id}/current-life/spirit-root` returns a spirit root assigned by Game Service.
* [x] Spirit root response includes `quality`, `label`, `elements`, `mutated_element`, and `variant_element`.
* [x] Tests cover the weighted quality buckets: pseudo (`quad`/`penta`), `triple`, `dual`, `variant`, and `celestial`.
* [x] Tests prove variant roots split `mutated_element` into one base five-element and one variant attribute.
* [x] Repeating spirit root detection for the same life returns the existing spirit root.
* [x] Unknown account IDs return a structured API error, not a traceback.
* [x] Tests cover success and not-found cases.
* [x] `pytest` and `ruff` pass.
* [x] `/docs` shows the new endpoints.

## Proposed API Contract

### `POST /api/v1/players/login`

Request:

```json
{
  "minecraft_uuid": "00000000-0000-0000-0000-000000000000",
  "player_name": "Steve"
}
```

Response:

```json
{
  "account": {
    "account_id": "uuid",
    "minecraft_uuid": "00000000-0000-0000-0000-000000000000",
    "player_name": "Steve"
  },
  "current_life": {
    "life_id": "uuid",
    "account_id": "uuid",
    "generation_no": 1,
    "status": "alive",
    "spirit_root": null
  }
}
```

### `POST /api/v1/players/{account_id}/current-life/spirit-root`

Response:

```json
{
  "life_id": "uuid",
  "spirit_root": {
    "quality": "dual",
    "label": "双灵根",
    "elements": ["金", "水"],
    "mutated_element": null,
    "variant_element": null
  },
  "already_detected": false
}
```

Variant example:

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

Spirit root distribution:

| Type | Probability | Contract |
|---|---:|---|
| 伪灵根（4-5系） | 60% | `quality: "quad"` or `quality: "penta"` |
| 三灵根 | 20% | `quality: "triple"` |
| 双灵根 | 12% | `quality: "dual"` |
| 异灵根（变异系） | 5% | `quality: "variant"` |
| 天灵根（单系） | 3% | `quality: "celestial"` |

Base elements:

```python
elements = ["金", "木", "水", "火", "土"]
```

Mutated elements:

```python
mutated_elements = ["火风", "木风", "金雷", "水雷", "火雷", "水冰", "木冰", "金暗", "土暗"]
```

Generation rules:

* Random generation must happen in two stages:
  1. Roll the spirit root type/quality bucket first: 天灵根 / 双灵根 / 三灵根 / 异灵根 / 伪灵根.
  2. After quality is known, draw the specific element composition for that quality.
* `quad`: choose 4 unique base elements.
* `penta`: use all 5 base elements.
* The 伪灵根 60% bucket is split evenly unless redesigned later:
  * `quad`: 30% total probability.
  * `penta`: 30% total probability.
* `triple`: choose 3 unique base elements.
* `dual`: choose 2 unique base elements.
* `variant`: choose 1 mutated element string from `mutated_elements`.
  * The mutated string contains one base five-element plus one variant attribute.
  * Example: `"金雷"` means base `elements: ["金"]`, `variant_element: "雷"`, `mutated_element: "金雷"`.
  * It must not be treated as two ordinary five-element roots.
* `celestial`: choose 1 base element.

## Technical Approach

* Add `player/schemas.py`, `player/repository.py`, `player/service.py`, and `player/api.py`.
* Use Pydantic schemas for API contracts.
* Use in-memory dictionaries inside a repository class for this task.
* Use deterministic Python-side service logic for idempotency:
  * Minecraft UUID maps to exactly one account.
  * Account maps to exactly one current generation-1 life.
  * A life with an existing spirit root does not reroll.
* Use `random.SystemRandom` or injectable roll/choice functions so tests can make spirit root selection deterministic without trusting client input.
* Add structured domain error handling for missing accounts.

## Decision (ADR-lite)

**Context**: The architecture wants PostgreSQL, but the project currently has no database layer. This task needs to make the first player flow visible in `/docs` without blocking on database/devops setup.

**Decision**: Use an in-memory repository for this task, but keep repository and service boundaries matching the future database shape.

**Consequences**: The API can be tested and exercised immediately. Data resets on service restart, so this is not a real save system. PostgreSQL models and migrations must be added before calling this "存档" or using it for a real server session.

## Out of Scope

* PostgreSQL, Redis, migrations, or durable save data.
* Paper Adapter plugin implementation.
* Authentication/security between Adapter and Game Service.
* Full reincarnation or multiple lives per account.
* Zone death behavior.
* Sect joining, techniques, combat, items, quests, breakthrough, or resource gain.
* Additional rare/special roots beyond the distribution listed in this PRD.

## Technical Notes

* This task is backend-only.
* It builds on `game-service/` from commit `1131190`.
* The current local docs page is available at `http://127.0.0.1:8000/docs` while the service is running.
* Future Paper Adapter validation will use these endpoints as the first login/character initialization contract.
