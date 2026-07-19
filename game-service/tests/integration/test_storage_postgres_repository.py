from __future__ import annotations

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.storage.postgres_repository import PostgresStorageRepository


async def hold_operation_lock(
    sessions: async_sessionmaker[AsyncSession],
    operation_id: UUID,
    staged: asyncio.Event,
    release: asyncio.Event,
) -> None:
    async with sessions() as session:
        await PostgresStorageRepository(session).lock_operation(operation_id)
        staged.set()
        await release.wait()
        await session.commit()


async def wait_for_database_lock(
    sessions: async_sessionmaker[AsyncSession],
    backend_pid: int,
) -> tuple[str, str]:
    async with sessions() as session:
        for _ in range(500):
            row = (
                await session.execute(
                    text(
                        "SELECT wait_event_type, wait_event "
                        "FROM pg_stat_activity WHERE pid = :pid"
                    ),
                    {"pid": backend_pid},
                )
            ).one_or_none()
            if row is not None and row.wait_event_type == "Lock":
                return str(row.wait_event_type), str(row.wait_event)
            await asyncio.sleep(0.01)
    raise AssertionError("Concurrent storage operation did not wait for a database lock")


@pytest.mark.asyncio
async def test_storage_operation_identity_is_serialized_by_advisory_lock(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    operation_id = UUID(int=70_001)
    staged = asyncio.Event()
    release = asyncio.Event()
    winner = asyncio.create_task(
        hold_operation_lock(postgres_sessions, operation_id, staged, release)
    )
    await staged.wait()

    async with postgres_sessions() as session:
        backend_pid = await session.scalar(text("SELECT pg_backend_pid()"))
        assert backend_pid is not None
        loser = asyncio.create_task(
            PostgresStorageRepository(session).lock_operation(operation_id)
        )
        wait_event = await wait_for_database_lock(postgres_sessions, backend_pid)
        release.set()
        await winner
        await loser
        await session.rollback()

    assert wait_event == ("Lock", "advisory")
