# Backend Directory Structure

> Target organization for the Python FastAPI Game Service.

## Current Status

No backend code exists yet. This file defines the initial structure future code should create. Update it with real file references after the first implementation slice lands.

## Target Layout

```text
game-service/
├── pyproject.toml
├── src/
│   └── immortal_mmo/
│       ├── main.py
│       ├── api/
│       │   ├── deps.py
│       │   └── v1/
│       │       ├── router.py
│       │       ├── player_routes.py
│       │       ├── item_routes.py
│       │       ├── quest_routes.py
│       │       ├── combat_routes.py
│       │       └── cultivation_routes.py
│       ├── core/
│       │   ├── config.py
│       │   ├── errors.py
│       │   ├── logging.py
│       │   └── time.py
│       ├── db/
│       │   ├── session.py
│       │   ├── base.py
│       │   └── migrations/
│       ├── player/
│       │   ├── models.py
│       │   ├── schemas.py
│       │   ├── repository.py
│       │   ├── service.py
│       │   └── api.py
│       ├── item/
│       ├── quest/
│       ├── combat/
│       └── cultivation/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

Use the same internal file pattern for each game module when relevant:

* `models.py`: persistence models for that module only
* `schemas.py`: Pydantic request/response/data-transfer schemas
* `repository.py`: database reads/writes owned by the module
* `service.py`: business rules and orchestration
* `api.py`: FastAPI route registrations for that module

## Module Boundaries

The module list comes from the architecture document:

* `player`: accounts, lives, player profile, login-linked state, sync state
* `item`: equipment, artifacts, affixes, durability, loot instances
* `quest`: quest state, dialogue choices, rewards
* `combat`: authoritative damage, skill execution, buffs
* `cultivation`: spirit roots, cultivation stage, breakthroughs, techniques

Rules:

* API handlers are thin. They validate request shape, call a service, and return a schema.
* Business rules live in `service.py`, not in route handlers or repositories.
* Repositories only access their own module's tables.
* Cross-module reads/writes go through another module's service interface.
* Shared code goes under `core/` only when it is truly cross-cutting. Do not create broad utility modules for domain logic.

## Adapter Boundary

When `minecraft-nodes/main-plugin/` is added, it should remain an Adapter Plugin:

```text
minecraft-nodes/
└── main-plugin/
    └── src/main/java/.../
        ├── event/       # Paper event listeners
        ├── client/      # HTTP client for Game Service
        └── presentation/# scoreboard, particles, UI, world effects
```

The adapter may report facts such as "player used skill X on target Y" or "player died in zone Z". It must not send trusted result numbers such as final damage, breakthrough success, reincarnation outcome, or loot eligibility.

## Naming Conventions

* Python packages and modules: `snake_case`
* Domain identifiers: stable string IDs, e.g. `spirit_root`, `cultivation_stage`, `technique_id`
* Database tables: plural `snake_case`
* Service functions: verb phrases, e.g. `create_life`, `resolve_player_death`, `calculate_damage`
* API routes: resource-oriented nouns, e.g. `/api/v1/players/{account_id}/current-life`

## Initial Example Pattern

This is a target pattern for the first implementation, not existing code:

```python
@router.post("/players/{account_id}/spirit-root", response_model=SpiritRootResult)
async def detect_spirit_root(
    account_id: UUID,
    service: PlayerService = Depends(get_player_service),
) -> SpiritRootResult:
    return await service.detect_spirit_root(account_id)
```

Keep the route small. Any random roll, account/life lookup, persistence, or audit event belongs in service/repository code.
