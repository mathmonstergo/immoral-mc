from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.item.models import InsufficientItemQuantity
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository


async def create_life(sessions: async_sessionmaker[AsyncSession]) -> UUID:
    async with sessions() as session:
        players = PostgresPlayerRepository(session)
        account = await players.upsert_account(uuid4(), "ItemTester")
        life = await players.insert_first_life(account.account_id)
        await session.commit()
        return life.life_id


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
            session_id=None,
            occurred_at=granted_at,
        )
        replay = await repository.consume(
            life_id=life_id,
            item_code="foundation_pill",
            quantity=1,
            operation_id=consume_operation,
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
                session_id=None,
                occurred_at=occurred_at,
            )
        await session.rollback()
