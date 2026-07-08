# Backend Directory Structure

> Target organization for the Python FastAPI Game Service.

## Current Status

The initial backend scaffold exists under `game-service/`.

## Target Layout

```text
game-service/
├── pyproject.toml
├── README.md
├── src/
│   └── immortal_mmo/
│       ├── main.py
│       ├── api/
│       │   └── v1/
│       │       ├── router.py
│       │       └── health.py
│       ├── core/
│       │   ├── config.py
│       │   ├── errors.py
│       │   ├── logging.py
│       │   └── time.py
│       ├── combat/
│       ├── cultivation/
│       ├── item/
│       ├── player/
│       │   ├── api.py
│       │   ├── repository.py
│       │   ├── schemas.py
│       │   └── service.py
│       └── quest/
└── tests/
    ├── integration/
    │   ├── test_health.py
    │   └── test_player_api.py
    └── unit/
        └── test_spirit_root_generation.py
```

When a game module gains real behavior, use this internal file pattern where relevant:

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

## Implemented Example Pattern

The current app factory lives in `game-service/src/immortal_mmo/main.py`:

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="Immortal MMO Game Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    return app
```

Keep `main.py` responsible for application assembly only. Put route behavior under `api/v1/`.

The current health route lives in `game-service/src/immortal_mmo/api/v1/router.py`:

```python
@api_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return get_health()
```

Future gameplay routes should stay similarly thin:

```python
@router.post("/players/{account_id}/spirit-root", response_model=SpiritRootResult)
async def detect_spirit_root(
    account_id: UUID,
    service: PlayerService = Depends(get_player_service),
) -> SpiritRootResult:
    return await service.detect_spirit_root(account_id)
```

Keep the route small. Any random roll, account/life lookup, persistence, or audit event belongs in service/repository code.

## Player Slice Pattern

The current player module follows:

* `player/api.py`: FastAPI routes and dependency lookup from `app.state`
* `player/service.py`: account/life orchestration and spirit root generation
* `player/repository.py`: temporary in-memory persistence behind a repository boundary
* `player/schemas.py`: Pydantic API and service contract models

The in-memory repository is an MVP adapter only. Preserve the service/repository boundary so PostgreSQL can replace it without changing API routes.
