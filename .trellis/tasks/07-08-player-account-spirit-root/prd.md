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
* Repeated spirit root detection for the same current life should return the existing result, not reroll.
* Use an in-memory repository for this task only, behind a service/repository boundary that can later be replaced with PostgreSQL.
* Include tests for account creation, idempotent lookup, first-life creation, spirit root detection, and detection idempotency.
* Keep the API shape stable enough for a future Paper Adapter to call.

## Acceptance Criteria

* [ ] `POST /api/v1/players/login` accepts Minecraft player identity and returns account plus current life.
* [ ] Repeating `POST /api/v1/players/login` with the same Minecraft UUID returns the same account/current life.
* [ ] `POST /api/v1/players/{account_id}/current-life/spirit-root` returns a spirit root assigned by Game Service.
* [ ] Repeating spirit root detection for the same life returns the existing spirit root.
* [ ] Unknown account IDs return a structured API error, not a traceback.
* [ ] Tests cover success and not-found cases.
* [ ] `pytest` and `ruff` pass.
* [ ] `/docs` shows the new endpoints.

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
  "spirit_root": "metal",
  "already_detected": false
}
```

Initial spirit roots:

```text
metal, wood, water, fire, earth
```

These are placeholders for the first executable slice; future game-design work can replace the list and weighting.

## Technical Approach

* Add `player/schemas.py`, `player/repository.py`, `player/service.py`, and `player/api.py`.
* Use Pydantic schemas for API contracts.
* Use in-memory dictionaries inside a repository class for this task.
* Use deterministic Python-side service logic for idempotency:
  * Minecraft UUID maps to exactly one account.
  * Account maps to exactly one current generation-1 life.
  * A life with an existing spirit root does not reroll.
* Use `random.SystemRandom` or an injectable chooser function so tests can make spirit root selection deterministic without trusting client input.
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
* Real spirit root probability design or rare/special roots.

## Technical Notes

* This task is backend-only.
* It builds on `game-service/` from commit `1131190`.
* The current local docs page is available at `http://127.0.0.1:8000/docs` while the service is running.
* Future Paper Adapter validation will use these endpoints as the first login/character initialization contract.
