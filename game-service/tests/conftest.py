from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tests.support.postgres import (
    MigratedPostgres,
    migrated_postgres_container,
    rollback_postgres_session,
)


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


@pytest_asyncio.fixture
async def postgres_session(postgres_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with rollback_postgres_session(postgres_engine) as session:
        yield session


@pytest_asyncio.fixture
async def clean_postgres_data(postgres_engine: AsyncEngine) -> AsyncIterator[None]:
    statement = text(
        """
        TRUNCATE TABLE
            technique_learn_operations,
            regional_storage_operations,
            regional_storage_slots,
            regional_storage_containers,
            item_instances,
            quest_cultivation_reward_claims,
            item_resource_entries,
            life_item_stacks,
            life_inventory_states,
            breakthrough_technique_debits,
            technique_investment_entries,
            cultivation_session_techniques,
            life_realm_entries,
            cultivation_resource_entries,
            quest_cultivation_reward_grants,
            life_cultivation_states,
            cultivation_sessions,
            life_techniques,
            life_mob_kill_counters,
            combat_kill_events,
            quest_reward_grants,
            quest_operations,
            quest_objective_progress,
            quest_progress,
            life_quest_states,
            life_spirit_roots,
            lives,
            account_minecraft_names,
            accounts
        """
    )
    async with postgres_engine.begin() as connection:
        await connection.execute(statement)
    yield
    async with postgres_engine.begin() as connection:
        await connection.execute(statement)
