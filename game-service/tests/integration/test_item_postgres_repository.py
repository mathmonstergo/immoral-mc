from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.item.db_models import ItemResourceEntryRow, LifeItemStackRow
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemOperationConflict,
)
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository


async def create_life(sessions: async_sessionmaker[AsyncSession]) -> UUID:
    async with sessions() as session:
        players = PostgresPlayerRepository(session)
        account = await players.upsert_account(uuid4(), "ItemTester")
        life = await players.insert_first_life(account.account_id)
        await session.commit()
        return life.life_id


async def hold_adjustment_until_released(
    sessions: async_sessionmaker[AsyncSession],
    *,
    life_id: UUID,
    item_code: str,
    operation_id: UUID,
    occurred_at: datetime,
    staged: asyncio.Event,
    release: asyncio.Event,
):
    async with sessions() as session:
        entry = await PostgresItemRepository(session).adjust(
            life_id=life_id,
            item_code=item_code,
            delta_quantity=1,
            operation_id=operation_id,
            occurred_at=occurred_at,
        )
        staged.set()
        await release.wait()
        await session.commit()
        return entry


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
    raise AssertionError("Concurrent item operation did not wait for a database lock")


@pytest.mark.asyncio
async def test_item_adjustment_and_consumption_are_audited_and_replayable(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    granted_at = datetime(2026, 7, 16, 8, tzinfo=UTC)
    grant_operation = uuid4()
    consume_operation = uuid4()

    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        granted = await repository.adjust(
            life_id=life_id,
            item_code="foundation_pill",
            delta_quantity=2,
            operation_id=grant_operation,
            occurred_at=granted_at,
        )
        consumed = await repository.consume(
            life_id=life_id,
            item_code="foundation_pill",
            quantity=1,
            operation_id=consume_operation,
            entry_type=ItemConsumptionType.QUEST_DELIVERY,
            session_id=None,
            occurred_at=granted_at,
        )
        replay = await repository.consume(
            life_id=life_id,
            item_code="foundation_pill",
            quantity=1,
            operation_id=consume_operation,
            entry_type=ItemConsumptionType.QUEST_DELIVERY,
            session_id=None,
            occurred_at=granted_at,
        )
        await session.commit()

    assert granted.balance_after == 2
    assert consumed.balance_after == 1
    assert replay == consumed


@pytest.mark.asyncio
async def test_consume_item_stack_rejects_insufficient_quantity(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    occurred_at = datetime(2026, 7, 16, 8, tzinfo=UTC)

    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        await repository.adjust(
            life_id=life_id,
            item_code="foundation_pill",
            delta_quantity=2,
            operation_id=uuid4(),
            occurred_at=occurred_at,
        )
        with pytest.raises(InsufficientItemQuantity):
            await repository.consume(
                life_id=life_id,
                item_code="foundation_pill",
                quantity=3,
                operation_id=uuid4(),
                entry_type=ItemConsumptionType.QUEST_DELIVERY,
                session_id=None,
                occurred_at=occurred_at,
            )
        await session.rollback()


@pytest.mark.asyncio
async def test_item_operation_replay_rejects_different_immutable_facts(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    occurred_at = datetime(2026, 7, 16, 8, tzinfo=UTC)
    operation_id = uuid4()

    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        granted = await repository.adjust(
            life_id=life_id,
            item_code="foundation_pill",
            delta_quantity=2,
            operation_id=operation_id,
            occurred_at=occurred_at,
        )
        with pytest.raises(ItemOperationConflict):
            await repository.consume(
                life_id=life_id,
                item_code="foundation_pill",
                quantity=1,
                operation_id=operation_id,
                entry_type=ItemConsumptionType.QUEST_DELIVERY,
                session_id=None,
                occurred_at=occurred_at,
            )
        await session.commit()

    async with postgres_sessions() as session:
        stack = await PostgresItemRepository(session).get_stack(
            life_id,
            "foundation_pill",
            for_update=False,
        )
    assert granted.balance_after == 2
    assert stack.quantity == 2


@pytest.mark.asyncio
async def test_concurrent_adjustment_across_lives_returns_stable_operation_conflict(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    winner_life_id = await create_life(postgres_sessions)
    loser_life_id = await create_life(postgres_sessions)
    operation_id = uuid4()
    occurred_at = datetime(2026, 7, 18, 8, tzinfo=UTC)
    winner_staged = asyncio.Event()
    release_winner = asyncio.Event()
    winner_task = asyncio.create_task(
        hold_adjustment_until_released(
            postgres_sessions,
            life_id=winner_life_id,
            item_code="shared_item",
            operation_id=operation_id,
            occurred_at=occurred_at,
            staged=winner_staged,
            release=release_winner,
        )
    )
    await asyncio.wait_for(winner_staged.wait(), timeout=5)
    loser_pid = asyncio.get_running_loop().create_future()

    async def run_loser():
        async with postgres_sessions() as session:
            backend_pid = await session.scalar(text("SELECT pg_backend_pid()"))
            assert backend_pid is not None
            loser_pid.set_result(int(backend_pid))
            result = await PostgresItemRepository(session).adjust(
                life_id=loser_life_id,
                item_code="shared_item",
                delta_quantity=1,
                operation_id=operation_id,
                occurred_at=occurred_at,
            )
            await session.commit()
            return result

    loser_task = asyncio.create_task(run_loser())
    try:
        wait_event = await wait_for_database_lock(
            postgres_sessions,
            await asyncio.wait_for(loser_pid, timeout=5),
        )
    except BaseException:
        release_winner.set()
        await asyncio.gather(winner_task, loser_task, return_exceptions=True)
        raise
    release_winner.set()
    winner_result, loser_result = await asyncio.gather(
        winner_task,
        loser_task,
        return_exceptions=True,
    )

    assert wait_event == ("Lock", "advisory")
    assert not isinstance(winner_result, BaseException)
    assert isinstance(loser_result, ItemOperationConflict)
    async with postgres_sessions() as session:
        entries = (
            await session.scalars(
                select(ItemResourceEntryRow).where(
                    ItemResourceEntryRow.operation_id == operation_id
                )
            )
        ).all()
        winner_stack = await session.get(
            LifeItemStackRow,
            (winner_life_id, "shared_item"),
        )
        loser_stack = await session.get(
            LifeItemStackRow,
            (loser_life_id, "shared_item"),
        )
    assert len(entries) == 1 and entries[0].life_id == winner_life_id
    assert winner_stack is not None and winner_stack.quantity == 1
    assert loser_stack is None


@pytest.mark.asyncio
async def test_concurrent_adjustment_conflicts_with_atomic_multi_item_delivery(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    winner_life_id = await create_life(postgres_sessions)
    delivery_life_id = await create_life(postgres_sessions)
    operation_id = uuid4()
    occurred_at = datetime(2026, 7, 18, 8, tzinfo=UTC)
    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        for item_code in ("item_alpha", "item_beta"):
            await repository.adjust(
                life_id=delivery_life_id,
                item_code=item_code,
                delta_quantity=1,
                operation_id=uuid4(),
                occurred_at=occurred_at,
            )
        await session.commit()

    winner_staged = asyncio.Event()
    release_winner = asyncio.Event()
    winner_task = asyncio.create_task(
        hold_adjustment_until_released(
            postgres_sessions,
            life_id=winner_life_id,
            item_code="item_alpha",
            operation_id=operation_id,
            occurred_at=occurred_at,
            staged=winner_staged,
            release=release_winner,
        )
    )
    await asyncio.wait_for(winner_staged.wait(), timeout=5)
    loser_pid = asyncio.get_running_loop().create_future()

    async def run_delivery():
        async with postgres_sessions() as session:
            backend_pid = await session.scalar(text("SELECT pg_backend_pid()"))
            assert backend_pid is not None
            loser_pid.set_result(int(backend_pid))
            result = await PostgresItemRepository(session).consume_many(
                life_id=delivery_life_id,
                consumptions=(
                    ItemConsumptionRequest(
                        item_code="item_beta",
                        quantity=1,
                        operation_id=operation_id,
                        entry_type=ItemConsumptionType.QUEST_DELIVERY,
                        session_id=None,
                        occurred_at=occurred_at,
                    ),
                    ItemConsumptionRequest(
                        item_code="item_alpha",
                        quantity=1,
                        operation_id=operation_id,
                        entry_type=ItemConsumptionType.QUEST_DELIVERY,
                        session_id=None,
                        occurred_at=occurred_at,
                    ),
                ),
            )
            await session.commit()
            return result

    delivery_task = asyncio.create_task(run_delivery())
    try:
        wait_event = await wait_for_database_lock(
            postgres_sessions,
            await asyncio.wait_for(loser_pid, timeout=5),
        )
    except BaseException:
        release_winner.set()
        await asyncio.gather(winner_task, delivery_task, return_exceptions=True)
        raise
    release_winner.set()
    winner_result, delivery_result = await asyncio.gather(
        winner_task,
        delivery_task,
        return_exceptions=True,
    )

    assert wait_event == ("Lock", "advisory")
    assert not isinstance(winner_result, BaseException)
    assert isinstance(delivery_result, ItemOperationConflict)
    async with postgres_sessions() as session:
        delivery_entries = (
            await session.scalars(
                select(ItemResourceEntryRow).where(
                    ItemResourceEntryRow.operation_id == operation_id,
                    ItemResourceEntryRow.entry_type == "quest_delivery",
                )
            )
        ).all()
        stacks = {
            item_code: await session.get(
                LifeItemStackRow,
                (delivery_life_id, item_code),
            )
            for item_code in ("item_alpha", "item_beta")
        }
    assert delivery_entries == []
    assert all(stack is not None and stack.quantity == 1 for stack in stacks.values())
