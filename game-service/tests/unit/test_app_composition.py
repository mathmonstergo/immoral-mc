import asyncio
import importlib
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository


def test_entrypoint_import_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    sys.modules.pop("immortal_mmo.entrypoint", None)

    with pytest.raises(ValidationError, match="database_url"):
        importlib.import_module("immortal_mmo.entrypoint")


def test_application_composition_requires_explicit_unit_of_work_factory() -> None:
    with pytest.raises(TypeError):
        create_app()


def test_production_modules_do_not_import_test_fakes_or_in_memory_repositories() -> None:
    package_root = Path(__file__).resolve().parents[2] / "src" / "immortal_mmo"
    forbidden_imports = ("tests.support", "FakeUnitOfWork", "InMemory")

    for module in package_root.rglob("*.py"):
        source = module.read_text()
        assert not any(name in source for name in forbidden_imports), module


@pytest.fixture
def production_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> object:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://immortal:immortal@127.0.0.1:5432/immortal",
    )
    sys.modules.pop("immortal_mmo.entrypoint", None)
    module = importlib.import_module("immortal_mmo.entrypoint")
    yield module
    sys.modules.pop("immortal_mmo.entrypoint", None)


def test_entrypoint_wires_only_postgresql_repositories(production_entrypoint: object) -> None:
    factory = production_entrypoint.uow_factory

    assert isinstance(factory, SqlAlchemyUnitOfWorkFactory)
    assert factory._player_repository_factory is PostgresPlayerRepository
    assert factory._quest_repository_factory is PostgresQuestRepository


@pytest.mark.asyncio
@pytest.mark.parametrize("shutdown_error", [RuntimeError("boom"), asyncio.CancelledError()])
async def test_entrypoint_disposes_engine_when_lifespan_exits_with_error(
    production_entrypoint: object,
    monkeypatch: pytest.MonkeyPatch,
    shutdown_error: BaseException,
) -> None:
    disposed = False

    class RecordingEngine:
        async def dispose(self) -> None:
            nonlocal disposed
            disposed = True

    monkeypatch.setattr(production_entrypoint, "engine", RecordingEngine())

    with pytest.raises(type(shutdown_error)):
        async with production_entrypoint.app.router.lifespan_context(
            production_entrypoint.app
        ):
            raise shutdown_error

    assert disposed is True
