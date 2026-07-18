import asyncio
import importlib
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import ValidationError

from immortal_mmo.combat.catalog import CombatRewardCatalog, load_combat_reward_catalog
from immortal_mmo.cultivation.realm_catalog import RealmCatalog, load_realm_catalog
from immortal_mmo.cultivation.technique_catalog import TechniqueCatalog, load_technique_catalog
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository


def test_entrypoint_import_requires_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("database_url", raising=False)
    sys.modules.pop("immortal_mmo.entrypoint", None)

    with pytest.raises(ValidationError, match="database_url"):
        importlib.import_module("immortal_mmo.entrypoint")


def test_application_composition_requires_explicit_unit_of_work_factory() -> None:
    with pytest.raises(TypeError):
        create_app()


def test_application_composition_preserves_a_falsey_readiness_check() -> None:
    class FalseyReadinessCheck:
        def __bool__(self) -> bool:
            return False

        async def __call__(self) -> object:
            raise AssertionError("not called by composition")

    readiness_check = FalseyReadinessCheck()
    app = create_app(
        uow_factory=lambda **kwargs: None,
        readiness_check=readiness_check,
    )

    assert app.state.readiness_check is readiness_check


def test_application_composition_shares_one_quest_catalog_with_combat_progression() -> None:
    custom_catalog = QuestDefinitionCatalog(
        quests=QUEST_CATALOG.quests,
        providers=QUEST_CATALOG.providers,
    )

    app = create_app(
        uow_factory=lambda **kwargs: None,
        quest_catalog=custom_catalog,
    )

    assert app.state.quest_service._catalog is custom_catalog
    assert app.state.combat_service._quest_progression._catalog is custom_catalog


def test_application_composition_shares_one_realm_catalog_with_combat_and_cultivation() -> None:
    custom_catalog = load_realm_catalog(
        Path(__file__).resolve().parents[2]
        / "src"
        / "immortal_mmo"
        / "cultivation"
        / "realm_catalog.json"
    )

    app = create_app(
        uow_factory=lambda **kwargs: None,
        realm_catalog=custom_catalog,
    )

    assert app.state.combat_service._realm_catalog is custom_catalog
    assert app.state.cultivation_service._realm_catalog is custom_catalog


def test_application_composition_shares_injected_technique_catalog() -> None:
    custom_catalog = load_technique_catalog(
        Path(__file__).resolve().parents[2]
        / "src"
        / "immortal_mmo"
        / "cultivation"
        / "techniques.json"
    )

    app = create_app(
        uow_factory=lambda **kwargs: None,
        technique_catalog=custom_catalog,
    )

    assert app.state.cultivation_service._technique_catalog is custom_catalog


def _catalog_with_objective(objective: object) -> QuestDefinitionCatalog:
    quest = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        objectives=(objective,),
    )
    return QuestDefinitionCatalog(
        quests=(quest,),
        providers=QUEST_CATALOG.providers,
    )


@pytest.mark.parametrize(
    ("objective", "catalog_kwargs", "message"),
    [
        (
            MythicMobKillObjectiveDefinition("kill", "击杀", "MissingMob", 1),
            {
                "combat_catalog": CombatRewardCatalog(
                    schema_version=1,
                    curves=(),
                    profiles=(),
                    mobs=(),
                )
            },
            "unknown MythicMob",
        ),
        (
            TechniqueLayerObjectiveDefinition("technique", "功法", "MissingTechnique", 1),
            {"technique_catalog": TechniqueCatalog(schema_version=1, techniques=())},
            "unknown technique",
        ),
        (
            RealmLevelObjectiveDefinition("realm", "境界", 22),
            {
                "realm_catalog": cast(
                    RealmCatalog,
                    SimpleNamespace(levels={1: object()}),
                )
            },
            "unknown realm level",
        ),
    ],
)
def test_application_composition_rejects_unknown_quest_objective_references(
    objective: object,
    catalog_kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_app(
            uow_factory=lambda **kwargs: None,
            quest_catalog=_catalog_with_objective(objective),
            **catalog_kwargs,
        )


def test_application_composition_accepts_typed_objectives_against_shared_catalogs() -> None:
    combat_catalog = load_combat_reward_catalog(
        Path(__file__).resolve().parents[2]
        / "src"
        / "immortal_mmo"
        / "combat"
        / "mythicmob_rewards.json"
    )
    technique_catalog = load_technique_catalog(
        Path(__file__).resolve().parents[2]
        / "src"
        / "immortal_mmo"
        / "cultivation"
        / "techniques.json"
    )
    realm_catalog = load_realm_catalog(
        Path(__file__).resolve().parents[2]
        / "src"
        / "immortal_mmo"
        / "cultivation"
        / "realm_catalog.json"
    )
    quest = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        objectives=(
            ItemDeliveryObjectiveDefinition("item", "交付", "foundation_pill", 1),
            MythicMobKillObjectiveDefinition(
                "kill",
                "击杀",
                next(iter(combat_catalog.mobs)),
                1,
            ),
            TechniqueLayerObjectiveDefinition(
                "technique",
                "功法",
                next(iter(technique_catalog.techniques)),
                1,
            ),
            RealmLevelObjectiveDefinition("realm", "境界", 1),
        ),
    )
    quest_catalog = QuestDefinitionCatalog(
        quests=(quest,),
        providers=QUEST_CATALOG.providers,
    )

    app = create_app(
        uow_factory=lambda **kwargs: None,
        combat_catalog=combat_catalog,
        technique_catalog=technique_catalog,
        realm_catalog=realm_catalog,
        quest_catalog=quest_catalog,
    )

    assert app.state.cultivation_service._technique_catalog is technique_catalog
    assert app.state.combat_service._quest_progression._catalog is quest_catalog


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
