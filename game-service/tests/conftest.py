from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.support.postgres import MigratedPostgres, migrated_postgres_container


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def migrated_postgres() -> AsyncIterator[MigratedPostgres]:
    async with migrated_postgres_container() as postgres:
        yield postgres


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def postgres_engine(migrated_postgres: MigratedPostgres) -> AsyncEngine:
    return migrated_postgres.engine


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def postgres_sessions(
    migrated_postgres: MigratedPostgres,
) -> async_sessionmaker[AsyncSession]:
    return migrated_postgres.sessions
