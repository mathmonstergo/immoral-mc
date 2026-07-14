# PostgreSQL Player and Quest Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Replace volatile player/quest state with a clean-break async PostgreSQL implementation that survives restarts and enforces account, life, spirit-root, quest, and idempotency invariants.

**Architecture:** First replace the synchronous application contracts with one async Unit of Work contract, explicit transactional fakes, and an app factory that cannot construct runtime storage implicitly. Then add SQLAlchemy async infrastructure, the initial Alembic schema, PostgreSQL Player/Quest repositories, and a PostgreSQL-only production entrypoint. There is no compatibility adapter, sync bridge, lease state machine, default in-memory repository, or data fallback.

**Tech Stack:** Python 3.12, FastAPI, Pydantic Settings, SQLAlchemy 2.x async ORM, asyncpg, Alembic, pytest, pytest-asyncio, testcontainers PostgreSQL, Ruff.

---

## File Map

- Create core async contracts in game-service/src/immortal_mmo/core/uow.py.
- Replace Player and Quest repository/service contracts directly; delete all old synchronous and lease/waiter APIs.
- Create explicit transactional fakes in game-service/tests/support/fakes.py.
- Replace game-service/src/immortal_mmo/main.py with an app factory requiring a UnitOfWorkFactory; it exports no default app.
- Create game-service/src/immortal_mmo/db/{base,session,uow}.py for SQLAlchemy metadata, sessions, and PostgreSQL UoW.
- Create module ORM rows and PostgreSQL repositories.
- Create game-service/migrations/** and game-service/alembic.ini for the initial schema.
- Create game-service/src/immortal_mmo/entrypoint.py as the only production app instance.
- Create PostgreSQL fixtures under game-service/tests/support/postgres.py.

## Clean-break gate

Every task below must leave the repository importable and its listed tests green. At no intermediate point may production code contain:

- InMemoryPlayerRepository or InMemoryQuestRepository;
- optional/default repository or UoW constructor arguments;
- synchronous service twins or sync-to-async wrappers;
- QuestOperationOwner, QuestOperationWaiter, leases, takeovers, mutation snapshots, or retry polling;
- a fallback app assembled without PostgreSQL-capable dependencies;
- old/new API versions running in parallel.

### Task 1: Cut the application layer over to async contracts and explicit fakes

**Files:**
- Modify: game-service/pyproject.toml
- Create: game-service/src/immortal_mmo/core/uow.py
- Create: game-service/src/immortal_mmo/player/models.py
- Replace: game-service/src/immortal_mmo/player/repository.py
- Replace: game-service/src/immortal_mmo/player/service.py
- Modify: game-service/src/immortal_mmo/player/schemas.py
- Modify: game-service/src/immortal_mmo/player/api.py
- Replace: game-service/src/immortal_mmo/quest/repository.py
- Replace: game-service/src/immortal_mmo/quest/service.py
- Modify: game-service/src/immortal_mmo/quest/api.py
- Modify: game-service/src/immortal_mmo/api/errors.py
- Replace: game-service/src/immortal_mmo/main.py
- Create: game-service/tests/support/__init__.py
- Create: game-service/tests/support/fakes.py
- Replace: game-service/tests/unit/test_quest_repository.py
- Modify: game-service/tests/unit/test_quest_service.py
- Modify: game-service/tests/unit/test_player_quest_facts.py
- Modify: game-service/tests/integration/test_player_api.py
- Modify: game-service/tests/integration/test_quest_api.py
- Modify: game-service/tests/integration/test_health.py

Replace the accidental httpx2 dependency with `httpx>=0.28.1` and add
`pytest-asyncio>=0.25.0` to the dev extra in this task before introducing async
tests. Database dependencies remain in Task 2.

- [ ] **Step 1: Write contract tests that require async services and explicit composition**

Add these assertions before changing production code:

~~~python
def test_create_app_requires_uow_factory() -> None:
    with pytest.raises(TypeError):
        create_app()


def test_services_require_uow_factory() -> None:
    with pytest.raises(TypeError):
        PlayerService()
    with pytest.raises(TypeError):
        QuestService()


def test_routes_are_async() -> None:
    assert inspect.iscoroutinefunction(login_player)
    assert inspect.iscoroutinefunction(detect_current_life_spirit_root)
    assert inspect.iscoroutinefunction(get_quest_interaction_state)
    assert inspect.iscoroutinefunction(accept_quest)
    assert inspect.iscoroutinefunction(turn_in_quest)
~~~

Delete the old tests for synchronous FastAPI threadpool dispatch, operation owners, waiters, leases, takeover, owner release, and mutation recovery snapshots. Do not rename those concepts.

- [ ] **Step 2: Introduce canonical internal Player models**

player/models.py contains persistence/application models only. Localized labels remain API presentation data.

~~~python
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

LifeStatus = Literal["alive", "reincarnated"]
SpiritRootQuality = Literal["quad", "penta", "triple", "dual", "variant", "celestial"]


@dataclass(frozen=True, slots=True)
class Account:
    account_id: UUID
    minecraft_uuid: UUID
    last_known_name: str
    revision: int


@dataclass(frozen=True, slots=True)
class Life:
    life_id: UUID
    account_id: UUID
    generation_no: int
    status: LifeStatus
    revision: int


@dataclass(frozen=True, slots=True)
class SpiritRoot:
    life_id: UUID
    quality_code: SpiritRootQuality
    base_element_codes: tuple[str, ...]
    variant_element_code: str | None
    generator_version: int


@dataclass(frozen=True, slots=True)
class CurrentLifeQuestFacts:
    account_id: UUID
    life_id: UUID
    generation_no: int
    spirit_root: SpiritRoot | None
    revision: int
~~~

The generator returns these English codes directly in canonical order:

~~~python
BASE_ELEMENT_ORDER = ("metal", "wood", "water", "fire", "earth")
VARIANT_ROOTS = (
    ("fire", "wind"), ("wood", "wind"), ("metal", "thunder"),
    ("water", "thunder"), ("fire", "thunder"), ("water", "ice"),
    ("wood", "ice"), ("metal", "dark"), ("earth", "dark"),
)
SPIRIT_ROOT_GENERATOR_VERSION = 1
~~~

Remove Chinese-to-English persistence conversion. player/schemas.py maps canonical codes to the single HTTP contract; it does not define repository models.

- [ ] **Step 3: Define complete async repository and Unit of Work protocols**

player/repository.py:

~~~python
class PlayerRepository(Protocol):
    async def upsert_account(self, minecraft_uuid: UUID, player_name: str) -> Account: ...
    async def lock_account(self, account_id: UUID) -> Account | None: ...
    async def get_current_life(self, account_id: UUID, *, for_update: bool = False) -> Life | None: ...
    async def get_lives(self, account_id: UUID) -> tuple[Life, ...]: ...
    async def insert_first_life(self, account_id: UUID) -> Life: ...
    async def get_spirit_root(self, life_id: UUID) -> SpiritRoot | None: ...
    async def insert_spirit_root(self, root: SpiritRoot) -> None: ...
    async def increment_life_revision(self, life_id: UUID) -> int: ...
    async def get_current_life_facts(self, account_id: UUID, *, for_update: bool = False) -> CurrentLifeQuestFacts: ...
~~~

quest/repository.py defines only compact durable concepts:

~~~python
class QuestOperationCommand(StrEnum):
    ACCEPT = "accept"
    TURN_IN = "turn_in"


@dataclass(frozen=True, slots=True)
class StoredQuestOperation:
    operation_id: UUID
    account_id: UUID
    life_id: UUID
    command: QuestOperationCommand
    quest_id: str
    provider_id: str
    request_fingerprint: str
    state: Literal["processing", "succeeded", "domain_failed"]
    changed: bool | None
    response_status: int | None
    response_content_type: str | None
    response_body: bytes | None
    response_contract_version: int | None


@dataclass(frozen=True, slots=True)
class FrozenHttpResponse:
    status_code: int
    content_type: str
    body: bytes
    contract_version: int


class QuestRepository(Protocol):
    async def get_operation(self, operation_id: UUID) -> StoredQuestOperation | None: ...
    async def reserve_operation(
        self,
        *,
        operation_id: UUID,
        account_id: UUID,
        life_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        request_fingerprint: str,
    ) -> bool: ...
    async def finalize_operation(
        self,
        operation_id: UUID,
        *,
        state: Literal["succeeded", "domain_failed"],
        changed: bool,
        response_status: int,
        response_content_type: str,
        response_body: bytes,
        response_contract_version: int,
    ) -> StoredQuestOperation: ...
    async def get_quest_revision(self, life_id: UUID, *, for_update: bool = False) -> int: ...
    async def increment_quest_revision(self, life_id: UUID) -> int: ...
    async def get_progresses(self, life_id: UUID, quest_ids: Collection[str]) -> dict[str, QuestProgress]: ...
    async def insert_progress(self, progress: QuestProgress) -> bool: ...
    async def complete_progress(self, life_id: UUID, quest_id: str, *, revision: int, completed_at: datetime) -> QuestProgress | None: ...
    async def get_progress(self, life_id: UUID, quest_id: str) -> QuestProgress | None: ...
~~~

core/uow.py is independent of SQLAlchemy:

~~~python
class UnitOfWork(Protocol):
    player: PlayerRepository
    quest: QuestRepository

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self, *, isolation: Literal["read_committed", "repeatable_read"] = "read_committed") -> UnitOfWork: ...
~~~

- [ ] **Step 4: Implement one transactional fake, not fake service twins**

tests/support/fakes.py contains FakeStore, FakePlayerRepository, FakeQuestRepository, FakeUnitOfWork, and FakeUnitOfWorkFactory. FakeUnitOfWork copies FakeStore on entry; commit replaces the shared state; rollback discards the copy. It implements the protocols above and uses one asyncio.Lock per factory so concurrent tests exercise one atomic transaction boundary.

Required fake behaviors:

- account upsert is keyed only by Minecraft UUID;
- the first login creates generation 1 once;
- historical lives without an alive life raise PlayerLifecycleError;
- spirit-root insert is one-per-life;
- quest operations are globally keyed by operation_id;
- operation reuse compares account, command, quest, provider, and fingerprint;
- progress insert/complete returns whether a durable change occurred;
- quest revision increments only after a durable progress change;
- committed frozen responses survive construction of a new service over the same FakeStore.

- [ ] **Step 5: Rewrite PlayerService and QuestService as async UoW consumers**

Define the new clean-break lifecycle/version errors before the services use
them:

~~~python
class PlayerLifecycleError(ConflictError):
    code = "player.lifecycle_unavailable"
    message = "The account has no active life; reincarnation is required."


class QuestDefinitionVersionMismatchError(ConflictError):
    code = "quest.definition_version_mismatch"
    message = "Stored quest progress does not match the active definition version."
~~~

Constructors require a UnitOfWorkFactory:

~~~python
class PlayerService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        spirit_root_generator: SpiritRootGenerator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._spirit_root_generator = spirit_root_generator or SpiritRootGenerator()


class QuestService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: QuestDefinitionCatalog = QUEST_CATALOG,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._clock = clock or (lambda: datetime.now(UTC))
~~~

Player login/detection and Quest reads/mutations each open their own UoW. Quest reads use repeatable_read. Quest mutations use read_committed and this exact order:

1. load/replay global operation;
2. lock account and current life;
3. recheck/reserve operation;
4. lock/lazily initialize quest revision;
5. load facts and progress from the same UoW;
6. validate definition version and rules;
7. conditionally mutate progress;
8. increment revision only when changed;
9. serialize success or domain failure once into frozen HTTP wire bytes;
10. finalize operation and commit;
11. return the same FrozenHttpResponse for success and domain failure after
    leaving the UoW; mutation failures do not pass through a second serializer.

Define QuestDefinitionVersionMismatchError in quest/service.py. Define one helper that computes lowercase SHA-256 over canonical JSON:

~~~python
def request_fingerprint(
    account_id: UUID,
    command: QuestOperationCommand,
    quest_id: str,
    provider_id: str,
) -> str:
    payload = json.dumps(
        {
            "account_id": str(account_id),
            "command": command.value,
            "contract_version": 1,
            "provider_id": provider_id,
            "quest_id": quest_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
~~~

For accept/turn-in with a new operation ID against an already active/completed row, load the existing row and return changed=false without incrementing revision. Same operation ID replays the original frozen response. Different operation IDs have distinct response operation_id values and are not asserted byte-identical.

Mutation routes await the service and return a Starlette Response built directly
from FrozenHttpResponse.body/status_code/content_type. The response model remains
only for OpenAPI documentation. Pre-reservation validation and unexpected
failures continue through the normal FastAPI error path.

api/errors.py exposes one serializer used by both ordinary DomainError handling
and Quest operation freezing:

~~~python
def serialize_domain_error(error: DomainError) -> bytes:
    return json.dumps(
        {"error": {"code": error.code, "message": error.message, "retryable": error.retryable}},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


async def domain_error_handler(request: Request, error: DomainError) -> Response:
    return Response(
        content=serialize_domain_error(error),
        status_code=error.status_code,
        media_type="application/json",
    )
~~~

- [ ] **Step 6: Replace app composition and async routes in the same commit**

main.py exports only:

~~~python
def create_app(*, uow_factory: UnitOfWorkFactory) -> FastAPI:
    app = FastAPI(title="Immortal MMO Game Service", version="0.1.0")
    app.state.player_service = PlayerService(uow_factory)
    app.state.quest_service = QuestService(uow_factory)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)
    return app
~~~

There is no module-level app and no optional arguments. All Player/Quest route handlers await service methods. API tests construct:

~~~python
store = FakeStore()
client = TestClient(create_app(uow_factory=FakeUnitOfWorkFactory(store)))
~~~

- [ ] **Step 7: Run the clean-break gate and commit**

~~~bash
cd game-service
.venv/bin/python -m pytest tests/unit tests/integration -q
.venv/bin/python -m ruff check src/immortal_mmo tests
! rg -n "InMemory(Player|Quest)Repository|QuestOperation(Owner|Waiter)|lease_expires|takeover|wait_for_operation|release_operation_owner" src tests
git add pyproject.toml src/immortal_mmo tests
git commit -m "refactor: cut application contracts over to async uow"
~~~

### Task 2: Add strict settings and SQLAlchemy async foundation

**Files:**
- Modify: game-service/pyproject.toml
- Replace: game-service/src/immortal_mmo/core/config.py
- Create: game-service/src/immortal_mmo/db/__init__.py
- Create: game-service/src/immortal_mmo/db/base.py
- Create: game-service/src/immortal_mmo/db/session.py
- Create: game-service/src/immortal_mmo/db/uow.py
- Create: game-service/tests/unit/test_config.py
- Create: game-service/tests/unit/test_database_factory.py

- [ ] **Step 1: Add dependencies and strict settings tests**

Add:

~~~toml
"sqlalchemy[asyncio]>=2.0.36",
"asyncpg>=0.30.0",
"alembic>=1.14.0",
"pydantic-settings>=2.7.0",
~~~

and the database integration-test dependency:

~~~toml
"testcontainers[postgresql]>=4.9.0",
~~~

Use _env_file=None in the missing URL test so a developer .env cannot invalidate it:

~~~python
def test_settings_require_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
~~~

- [ ] **Step 2: Implement strict settings**

~~~python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=100)
    database_pool_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    database_echo: bool = False
~~~

- [ ] **Step 3: Implement metadata, engine, and session factory**

~~~python
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
~~~

- [ ] **Step 4: Implement SQLAlchemy UoW against the already-defined protocols**

~~~python
class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        sessions,
        isolation: Literal["read_committed", "repeatable_read"],
        player_repository_factory,
        quest_repository_factory,
    ) -> None:
        self._sessions = sessions
        self._isolation = isolation
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory

    async def __aenter__(self):
        self.session = self._sessions()
        level = "REPEATABLE READ" if self._isolation == "repeatable_read" else "READ COMMITTED"
        await self.session.connection(execution_options={"isolation_level": level})
        self.player = self._player_repository_factory(self.session)
        self.quest = self._quest_repository_factory(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session.in_transaction():
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
~~~

To keep this task importable before repository implementation, db/uow.py imports repository factories through two injected callables:

~~~python
class SqlAlchemyUnitOfWorkFactory:
    def __init__(self, sessions, player_repository_factory, quest_repository_factory):
        self._sessions = sessions
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory

    def __call__(self, *, isolation="read_committed"):
        return SqlAlchemyUnitOfWork(
            self._sessions,
            isolation,
            self._player_repository_factory,
            self._quest_repository_factory,
        )
~~~

The test passes recording repository factories; no stub production repository classes are created.

- [ ] **Step 5: Test and commit**

~~~bash
cd game-service
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest tests/unit/test_config.py tests/unit/test_database_factory.py -q
.venv/bin/python -m ruff check src/immortal_mmo/core/config.py src/immortal_mmo/db tests/unit/test_config.py tests/unit/test_database_factory.py
git add pyproject.toml src/immortal_mmo/core/config.py src/immortal_mmo/db tests/unit/test_config.py tests/unit/test_database_factory.py
git commit -m "feat: add async database foundation"
~~~

### Task 3: Add ORM rows, PostgreSQL fixtures, and the initial migration

**Files:**
- Create: game-service/src/immortal_mmo/player/db_models.py
- Create: game-service/src/immortal_mmo/quest/db_models.py
- Create: game-service/alembic.ini
- Create: game-service/migrations/env.py
- Create: game-service/migrations/script.py.mako
- Create: game-service/migrations/versions/20260714_001_player_quest_persistence.py
- Create: game-service/tests/conftest.py
- Create: game-service/tests/support/postgres.py
- Create: game-service/tests/integration/test_migrations.py

- [ ] **Step 1: Build a real PostgreSQL fixture**

tests/support/postgres.py must:

- start PostgresContainer("postgres:17-alpine");
- convert the returned URL to postgresql+asyncpg;
- set sqlalchemy.url for Alembic without mutating process-global DATABASE_URL;
- run alembic upgrade head through Config;
- create an async engine/session factory;
- dispose the engine and stop the container in fixture teardown.

tests/conftest.py registers pytest_asyncio fixtures for migrated_postgres, postgres_engine, and postgres_sessions. It is a new file.

- [ ] **Step 2: Write migration tests before the migration**

Tests must assert:

- the seven gameplay tables are present and alembic_version is present separately;
- named primary/foreign/unique/check constraints;
- ix_account_names_normalized;
- ux_lives_one_alive_per_account;
- ix_quest_progress_active_life;
- ix_quest_progress_revision;
- ix_quest_operations_account_created;
- life, spirit-root, quest-progress, and quest-operation immutability triggers
  and their functions;
- invalid name, duplicate alive life, invalid terminal fields, invalid root, and incomplete finalized operation all fail;
- reincarnated life and spirit-root update/delete fail;
- quest progress only permits identity-preserving active-to-completed updates
  with an advancing revision and cannot be deleted;
- finalized quest operations cannot be rewritten or deleted;
- alembic current equals 20260714_001.

- [ ] **Step 3: Implement complete typed ORM rows**

Use Mapped[UUID], PostgreSQL UUID/ARRAY types, DateTime(timezone=True), explicit nullable values, server defaults matching the migration, and named constraints matching the approved design. ORM rows contain no relationships with cascade delete.

- [ ] **Step 4: Implement the migration from the approved DDL**

The migration implements sections 4.1 through 4.7 of docs/superpowers/specs/2026-07-14-minecraft-postgresql-schema-design.md exactly, including the full active-to-completed quest-progress trigger, finalized-operation immutability trigger, BYTEA response body, and response content type.

The downgrade drops triggers before functions, child tables before parent tables, then all indexes/functions. No legacy IDs, cultivation values, operation archive, lease, owner, waiter, or snapshot columns are created.

- [ ] **Step 5: Test, lint, and commit every created fixture**

~~~bash
cd game-service
.venv/bin/python -m pytest tests/integration/test_migrations.py -q
.venv/bin/python -m ruff check src/immortal_mmo/player/db_models.py src/immortal_mmo/quest/db_models.py migrations tests/conftest.py tests/support/postgres.py tests/integration/test_migrations.py
git add alembic.ini migrations src/immortal_mmo/player/db_models.py src/immortal_mmo/quest/db_models.py tests/conftest.py tests/support/postgres.py tests/integration/test_migrations.py
git commit -m "feat: add player and quest database schema"
~~~

### Task 4: Implement PostgreSQL Player persistence

**Files:**
- Create: game-service/src/immortal_mmo/player/postgres_repository.py
- Create: game-service/src/immortal_mmo/player/mappers.py
- Modify: game-service/src/immortal_mmo/player/service.py
- Modify: game-service/src/immortal_mmo/player/schemas.py
- Modify: game-service/src/immortal_mmo/player/api.py
- Create: game-service/tests/integration/test_player_repository.py
- Modify: game-service/tests/integration/test_player_api.py
- Modify: game-service/tests/unit/test_spirit_root_generation.py
- Modify: game-service/tests/unit/test_player_quest_facts.py

- [ ] **Step 1: Add failing repository and API validation tests**

Cover:

- concurrent first login creates one account and one alive life;
- name changes update last-known casing/history and increment account revision once;
- repeated same-name login updates timestamps without incrementing revision;
- Java name validation [A-Za-z0-9_]{3,16} returns HTTP 422 before SQL;
- historical lives without an alive life raise PlayerLifecycleError;
- a second alive life is rejected;
- concurrent root detection creates one immutable canonical result;
- restart/new sessions return the same account, life, name history, and root.

- [ ] **Step 2: Implement account/name/current-life SQL**

Account upsert updates last_known_name, timestamps, and revision only when the name changes. After the upsert:

1. upsert account_minecraft_names by (account_id, normalized_name);
2. lock accounts by account_id;
3. query status=alive;
4. if no alive row and no history, insert generation 1;
5. if no alive row and history exists, raise PlayerLifecycleError;
6. commit through PlayerService.

Catch only retryable serialization/unique races at the service transaction boundary and retry the complete login transaction once. Do not catch IntegrityError and continue in an aborted session.

- [ ] **Step 3: Implement immutable root detection**

Lock current life, return the existing root when present, otherwise generate one canonical SpiritRoot with generator_version=1, insert it, and atomically increment lives.revision. The mapper derives API label/mutated display fields; the repository never accepts localized strings.

- [ ] **Step 4: Wire PostgreSQL repository factory into UoW tests**

Construct:

~~~python
factory = SqlAlchemyUnitOfWorkFactory(
    postgres_sessions,
    PostgresPlayerRepository,
    NoOpQuestRepository,
)
~~~

Until Task 5, integration tests that only use Player pass a NoOpQuestRepository test factory implementing the current protocol and raising AssertionError if called. It lives in tests/support/fakes.py, never production code.

- [ ] **Step 5: Run and commit**

~~~bash
cd game-service
.venv/bin/python -m pytest tests/integration/test_player_repository.py tests/integration/test_player_api.py tests/unit/test_spirit_root_generation.py tests/unit/test_player_quest_facts.py -q
.venv/bin/python -m ruff check src/immortal_mmo/player tests/support/fakes.py tests/integration/test_player_repository.py tests/integration/test_player_api.py
git add src/immortal_mmo/player tests/support/fakes.py tests/integration/test_player_repository.py tests/integration/test_player_api.py tests/unit/test_spirit_root_generation.py tests/unit/test_player_quest_facts.py
git commit -m "feat: persist accounts lives and spirit roots"
~~~

### Task 5: Implement PostgreSQL Quest transactions and exact replay

**Files:**
- Create: game-service/src/immortal_mmo/quest/postgres_repository.py
- Modify: game-service/src/immortal_mmo/quest/repository.py
- Modify: game-service/src/immortal_mmo/quest/service.py
- Modify: game-service/src/immortal_mmo/quest/api.py
- Modify: game-service/src/immortal_mmo/api/errors.py
- Create: game-service/tests/integration/test_quest_postgres_repository.py
- Modify: game-service/tests/integration/test_quest_api.py
- Modify: game-service/tests/unit/test_quest_repository.py
- Modify: game-service/tests/unit/test_quest_service.py

- [ ] **Step 1: Add distinct idempotency/concurrency tests**

Test separately:

- same operation ID concurrently/repeatedly returns identical status, content
  type, and response bytes;
- different operation IDs accepting concurrently create one progress change, one changed=true response, and one changed=false response;
- different operation IDs turning in concurrently complete once with the same revision behavior;
- same operation ID with another account/command/quest/provider/fingerprint returns idempotency conflict;
- domain failure commits and replays identical status/content-type/body bytes;
- transaction failure leaves neither progress nor operation;
- definition-version mismatch fails fast;
- restart preserves progress, revision, success replay, and failure replay;
- after direct test-only reincarnation/new-life setup, retrying the old global operation replays its old-life result.

- [ ] **Step 2: Implement global operation reservation**

Use INSERT ... ON CONFLICT (operation_id) DO NOTHING RETURNING. A returned row owns the operation in the current transaction. No returned row means load the committed row, compare the complete identity, and either replay or raise QuestIdempotencyConflictError. Never use a plain unique violation as flow control.

- [ ] **Step 3: Implement revision and conditional progress branches**

Lazily insert life_quest_states revision 0 and lock it. For accept:

- insert progress conditionally;
- if inserted, increment aggregate revision and return changed=true;
- if not inserted, load the existing row, verify definition version, do not increment, return changed=false.

For turn-in:

- update only status=active;
- if updated, increment revision and return changed=true;
- if not updated, load the row;
- missing row is QuestNotAcceptedError;
- completed row returns changed=false without revision increment.

- [ ] **Step 4: Preserve exact frozen HTTP bytes**

Use the FrozenHttpResponse contract defined in Task 1:

~~~python
@dataclass(frozen=True, slots=True)
class FrozenHttpResponse:
    status_code: int
    content_type: str
    body: bytes
    contract_version: int
~~~

Serialize and validate the response once before finalization. Persist body exactly
as BYTEA together with response_content_type. The first request and every replay
return Response(content=result.body, status_code=result.status_code,
media_type=result.content_type); do not parse into a Pydantic model and
reserialize.

For committed domain failures, finalize and commit the same FrozenHttpResponse
shape and return it to the mutation route. Do not raise a reconstructed
DomainError after commit. Non-operation domain errors continue to use the normal
structured handler, and both paths share one error-envelope serializer.

- [ ] **Step 5: Verify bounded queries**

Instrument SQLAlchemy before_cursor_execute in tests. Provider inspection must use a bounded aggregate query count independent of quest count; it may not query once per quest/objective. EXPLAIN the current-life query and assert ux_lives_one_alive_per_account is used after ANALYZE.

- [ ] **Step 6: Run and commit**

~~~bash
cd game-service
.venv/bin/python -m pytest tests/unit/test_quest_repository.py tests/unit/test_quest_service.py tests/integration/test_quest_postgres_repository.py tests/integration/test_quest_api.py -q
.venv/bin/python -m ruff check src/immortal_mmo/quest src/immortal_mmo/api/errors.py tests/unit/test_quest_repository.py tests/unit/test_quest_service.py tests/integration/test_quest_postgres_repository.py tests/integration/test_quest_api.py
git add src/immortal_mmo/quest src/immortal_mmo/api/errors.py tests/unit/test_quest_repository.py tests/unit/test_quest_service.py tests/integration/test_quest_postgres_repository.py tests/integration/test_quest_api.py
git commit -m "feat: persist quest progress and exact idempotency replay"
~~~

### Task 6: Build the PostgreSQL-only production entrypoint and readiness

**Files:**
- Create: game-service/src/immortal_mmo/entrypoint.py
- Modify: game-service/src/immortal_mmo/main.py
- Modify: game-service/src/immortal_mmo/api/v1/health.py
- Modify: game-service/src/immortal_mmo/api/v1/router.py
- Create: game-service/tests/unit/test_app_composition.py
- Modify: game-service/tests/integration/test_health.py

- [ ] **Step 1: Add production composition tests**

Assert entrypoint import with no DATABASE_URL fails settings validation, create_app still requires explicit UoW, and no production module imports a fake repository.

- [ ] **Step 2: Create one production app**

entrypoint.py creates Settings, engine, sessions, UoW factory with PostgresPlayerRepository/PostgresQuestRepository, and app. Pass an async lifespan into create_app so engine.dispose() always runs.

- [ ] **Step 3: Add readiness**

/health remains process liveness. /ready:

1. executes SELECT 1;
2. reads the single alembic_version value;
3. reads code head through Alembic ScriptDirectory;
4. returns 200 with migration_revision when equal;
5. returns 503 for connectivity, missing/multiple revision rows, or mismatch.

Tests cover all five outcomes using explicit dependencies; readiness never runs migrations.

- [ ] **Step 4: Run and commit**

~~~bash
cd game-service
.venv/bin/python -m pytest tests/unit/test_app_composition.py tests/integration/test_health.py -q
.venv/bin/python -m ruff check src/immortal_mmo/main.py src/immortal_mmo/entrypoint.py src/immortal_mmo/api tests/unit/test_app_composition.py tests/integration/test_health.py
git add src/immortal_mmo/main.py src/immortal_mmo/entrypoint.py src/immortal_mmo/api tests/unit/test_app_composition.py tests/integration/test_health.py
git commit -m "feat: require PostgreSQL in production"
~~~

### Task 7: Add local PostgreSQL workflow and operational recovery documentation

**Files:**
- Create: compose.yaml
- Create: game-service/.env.example
- Modify: scripts/start-game-service.sh
- Modify: game-service/README.md
- Modify: .trellis/spec/backend/database-guidelines.md only for conventions proven by implementation

- [ ] **Step 1: Add PostgreSQL 17 local service**

Use postgres:17-alpine, localhost-only port publishing, a named volume, pg_isready, and development-only credentials.

- [ ] **Step 2: Replace the startup command**

scripts/start-game-service.sh installs dependencies, requires DATABASE_URL, runs no migration automatically, and execs:

~~~bash
.venv/bin/python -m uvicorn immortal_mmo.entrypoint:app --host 127.0.0.1 --port 8000
~~~

- [ ] **Step 3: Document migration/reset/backup/restore**

README includes exact commands for docker compose up, alembic upgrade head, starting the service, an explicit disposable-development volume reset, pg_dump, restoring into a second isolated database, running alembic current there, and executing the restart smoke against the restored database.

- [ ] **Step 4: Validate and commit**

~~~bash
bash -n scripts/start-game-service.sh
git diff --check
git add compose.yaml game-service/.env.example scripts/start-game-service.sh game-service/README.md
git add .trellis/spec/backend/database-guidelines.md
git commit -m "docs: add PostgreSQL workflow and recovery drill"
~~~

### Task 8: Run full verification, restart smoke, and clean-break audit

**Files:**
- Modify only verified defects revealed by these checks.

- [ ] **Step 1: Verify a new database**

~~~bash
docker compose up -d postgres
cd game-service
.venv/bin/alembic upgrade head
.venv/bin/alembic current
~~~

Expected: 20260714_001 at head.

- [ ] **Step 2: Run backend checks**

~~~bash
cd game-service
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
~~~

- [ ] **Step 3: Audit removal of the old architecture**

~~~bash
! rg -n "InMemory(Player|Quest)Repository|QuestOperation(Owner|Waiter)|lease_expires|wait_for_operation|release_operation_owner|sync_to_async|run_in_threadpool" game-service/src game-service/tests
! rg -n "repository: .*\| None|uow_factory: .*\| None" game-service/src/immortal_mmo/player game-service/src/immortal_mmo/quest
~~~

- [ ] **Step 4: Run Java regression checks**

~~~bash
cd minecraft-nodes/main-plugin
./gradlew test build
~~~

If the single chosen HTTP contract changed, update the Paper records/client/tests in the same defect-fix commit. Do not add compatibility endpoints or alternate payload parsers.

- [ ] **Step 5: Perform restart and restore smoke**

Use a fixed UUID and operation IDs:

1. login;
2. detect root;
3. accept first-steps;
4. restart Game Service;
5. verify same account/life/root/progress and byte-identical replay;
6. turn in and restart;
7. verify completion;
8. pg_dump;
9. restore to an empty second database;
10. start against the restored database and repeat all reads/replays.

- [ ] **Step 6: Run Trellis quality check**

Run trellis-check, fix findings, and rerun Ruff, pytest, Gradle, restart smoke, and restore smoke after the last fix.

### Task 9: Finish, archive, and notify

**Files:**
- Update specs only for concrete conventions learned during implementation.
- Archive .trellis/tasks/07-14-postgresql-schema-design through Trellis.
- Record the session journal through trellis-finish-work.

- [ ] **Step 1: Record evidence**

Record Alembic revision, Ruff result, pytest count, Gradle result, clean-break scan, restart smoke, dump/restore smoke, and final commits.

- [ ] **Step 2: Finish Trellis workflow**

Run trellis-update-spec only when implementation established a reusable convention, then run trellis-finish-work after all checks pass.

- [ ] **Step 3: Send one completion email**

Send to 1094005479@qq.com with schema/refactor summary, verification counts, commit hashes, recovery drill result, and the recommended next gameplay vertical slice.
