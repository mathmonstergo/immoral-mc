from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

GAME_SERVICE_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class MigratedPostgres:
    url: str
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    server_version: str


def _asyncpg_url(container: PostgresContainer) -> str:
    return make_url(container.get_connection_url()).set(
        drivername="postgresql+asyncpg"
    ).render_as_string(hide_password=False)


def _upgrade_to_head(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def alembic_config(database_url: str) -> Config:
    config = Config(str(GAME_SERVICE_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def migrate_postgres(database_url: str, revision: str) -> None:
    command.upgrade(alembic_config(database_url), revision)


def downgrade_postgres(database_url: str, revision: str) -> None:
    command.downgrade(alembic_config(database_url), revision)


def check_migration_metadata(database_url: str) -> None:
    command.check(alembic_config(database_url))


@asynccontextmanager
async def migrated_postgres_container() -> AsyncIterator[MigratedPostgres]:
    container = PostgresContainer("postgres:17-alpine")
    engine: AsyncEngine | None = None
    await asyncio.to_thread(container.start)
    try:
        database_url = _asyncpg_url(container)
        await asyncio.to_thread(_upgrade_to_head, database_url)
        engine = create_async_engine(database_url, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with engine.connect() as connection:
            server_version = str(
                (await connection.execute(text("SHOW server_version"))).scalar_one()
            )
        yield MigratedPostgres(
            url=database_url,
            engine=engine,
            sessions=sessions,
            server_version=server_version,
        )
    finally:
        if engine is not None:
            await engine.dispose()
        await asyncio.to_thread(container.stop)
