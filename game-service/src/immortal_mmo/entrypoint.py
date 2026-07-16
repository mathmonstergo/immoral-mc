from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI

from immortal_mmo.api.v1.health import PostgresReadinessChecker
from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.core.config import Settings
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.session import create_engine, create_session_factory
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository

GAME_SERVICE_ROOT = Path(__file__).resolve().parents[2]

settings = Settings()
engine = create_engine(settings)
sessions = create_session_factory(engine)
uow_factory = SqlAlchemyUnitOfWorkFactory(
    sessions,
    PostgresPlayerRepository,
    PostgresQuestRepository,
    PostgresCombatRepository,
    PostgresCultivationRepository,
    PostgresItemRepository,
)
alembic_config = Config(str(GAME_SERVICE_ROOT / "alembic.ini"))
script_directory = ScriptDirectory.from_config(alembic_config)
readiness_check = PostgresReadinessChecker(sessions, script_directory)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    try:
        yield
    finally:
        await engine.dispose()


app = create_app(
    uow_factory=uow_factory,
    lifespan=lifespan,
    readiness_check=readiness_check,
)
