import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.api.v1 import health as health_module
from immortal_mmo.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint_reports_service_status() -> None:
    app = create_app(uow_factory=FakeUnitOfWorkFactory(FakeStore()))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "game-service",
        "status": "ok",
        "version": "0.1.0",
    }


class FixedReadinessCheck:
    def __init__(self, result: object) -> None:
        self._result = result

    async def __call__(self) -> object:
        return self._result


@pytest.mark.asyncio
async def test_ready_reports_the_matching_migration_revision() -> None:
    app = create_app(
        uow_factory=FakeUnitOfWorkFactory(FakeStore()),
        readiness_check=FixedReadinessCheck(
            health_module.ReadinessResult(
                ready=True,
                migration_revision="20260714_001",
            )
        ),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "migration_revision": "20260714_001",
    }


@pytest.mark.asyncio
async def test_ready_returns_structured_503_when_readiness_fails() -> None:
    app = create_app(
        uow_factory=FakeUnitOfWorkFactory(FakeStore()),
        readiness_check=FixedReadinessCheck(health_module.ReadinessResult(ready=False)),
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service.not_ready",
            "message": "The service is not ready.",
            "retryable": True,
        }
    }


class FixedScriptDirectory:
    def __init__(self, heads: tuple[str, ...]) -> None:
        self._heads = heads

    def get_heads(self) -> list[str]:
        return list(self._heads)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("database_revisions", "code_heads"),
    [
        ((), ("20260714_001",)),
        (("20260714_001", "other"), ("20260714_001",)),
        (("20260714_001",), ()),
        (("20260714_001",), ("20260714_001", "other")),
        (("20260714_001",), ("other",)),
    ],
)
async def test_readiness_rejects_invalid_database_or_code_revision_cardinality(
    postgres_sessions: async_sessionmaker[AsyncSession],
    database_revisions: tuple[str, ...],
    code_heads: tuple[str, ...],
) -> None:
    async with postgres_sessions() as session:
        await session.execute(text("DELETE FROM alembic_version"))
        for revision in database_revisions:
            await session.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": revision},
            )
        await session.commit()

    try:
        result = await health_module.PostgresReadinessChecker(
            postgres_sessions,
            FixedScriptDirectory(code_heads),
        )()
    finally:
        async with postgres_sessions() as session:
            await session.execute(text("DELETE FROM alembic_version"))
            await session.execute(
                text("INSERT INTO alembic_version (version_num) VALUES ('20260714_001')")
            )
            await session.commit()

    assert result == health_module.ReadinessResult(ready=False)


@pytest.mark.asyncio
async def test_readiness_queries_connectivity_and_exact_revision_rows(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    result = await health_module.PostgresReadinessChecker(
        postgres_sessions,
        FixedScriptDirectory(("20260714_001",)),
    )()

    assert result == health_module.ReadinessResult(
        ready=True,
        migration_revision="20260714_001",
    )


class FailingSessionFactory:
    def __call__(self) -> object:
        raise OSError("database unavailable")


@pytest.mark.asyncio
async def test_readiness_returns_not_ready_for_connectivity_or_query_failure() -> None:
    result = await health_module.PostgresReadinessChecker(
        FailingSessionFactory(),
        FixedScriptDirectory(("20260714_001",)),
    )()

    assert result == health_module.ReadinessResult(ready=False)


class BrokenSessionFactory:
    def __call__(self) -> object:
        raise RuntimeError("programming error")


@pytest.mark.asyncio
async def test_readiness_does_not_hide_unexpected_programming_errors() -> None:
    checker = health_module.PostgresReadinessChecker(
        BrokenSessionFactory(),
        FixedScriptDirectory(("20260714_001",)),
    )

    with pytest.raises(RuntimeError, match="programming error"):
        await checker()
