from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.db_models import CombatKillEventRow, LifeMobKillCounterRow
from immortal_mmo.combat.models import CombatKillEvent
from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import (
    CultivationResourceEntryRow,
    LifeCultivationStateRow,
)
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository

OCCURRED_AT = datetime(2026, 7, 15, 12, tzinfo=UTC)


async def create_player_life(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID, UUID]:
    minecraft_uuid = uuid4()
    async with sessions() as session:
        players = PostgresPlayerRepository(session)
        account = await players.upsert_account(minecraft_uuid, "Combatant")
        life = await players.insert_first_life(account.account_id)
        await session.commit()
    return minecraft_uuid, account.account_id, life.life_id


def kill_event(
    *,
    minecraft_uuid: UUID,
    account_id: UUID,
    life_id: UUID,
    source_event_id: UUID | None = None,
) -> CombatKillEvent:
    return CombatKillEvent(
        kill_event_id=uuid4(),
        source_event_id=source_event_id or uuid4(),
        server_id="main-1",
        entity_uuid=uuid4(),
        mob_internal_name="AzureWolf",
        mob_level=Decimal("12.000"),
        killer_minecraft_uuid=minecraft_uuid,
        source_life_id=life_id,
        attribution_kind="damage_over_time",
        technique_id="venom_mist",
        cast_id=uuid4(),
        account_id=account_id,
        life_id=life_id,
        world_key="minecraft:overworld",
        occurred_at=OCCURRED_AT,
        outcome="rewarded",
        telemetry="compact",
        detail_payload=None,
        reward_amount=120,
    )


@pytest.mark.asyncio
async def test_player_repository_locks_account_by_minecraft_uuid_for_combat(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    minecraft_uuid, account_id, _ = await create_player_life(postgres_sessions)

    async with postgres_sessions() as session:
        account = await PostgresPlayerRepository(session).lock_account_by_minecraft_uuid(
            minecraft_uuid
        )
        await session.rollback()

    assert account is not None
    assert account.account_id == account_id


@pytest.mark.asyncio
async def test_combat_repository_deduplicates_source_and_increments_counter(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    minecraft_uuid, account_id, life_id = await create_player_life(postgres_sessions)
    event = kill_event(
        minecraft_uuid=minecraft_uuid,
        account_id=account_id,
        life_id=life_id,
    )

    async with postgres_sessions() as session:
        repository = PostgresCombatRepository(session)
        assert await repository.insert_event_if_absent(event) is True
        assert await repository.insert_event_if_absent(event) is False
        assert await repository.increment_mob_counter(
            life_id,
            "AzureWolf",
            OCCURRED_AT,
        ) == 1
        assert await repository.increment_mob_counter(
            life_id,
            "AzureWolf",
            OCCURRED_AT,
        ) == 2
        await session.commit()

    async with postgres_sessions() as session:
        stored = await PostgresCombatRepository(session).get_event(event.source_event_id)
        counter = await session.scalar(
            select(LifeMobKillCounterRow).where(
                LifeMobKillCounterRow.life_id == life_id,
                LifeMobKillCounterRow.mob_internal_name == "AzureWolf",
            )
        )

    assert stored == event
    assert counter is not None
    assert counter.kill_count == 2


@pytest.mark.asyncio
async def test_cultivation_repository_credits_ledger_and_balance_atomically(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    minecraft_uuid, account_id, life_id = await create_player_life(postgres_sessions)
    event = kill_event(
        minecraft_uuid=minecraft_uuid,
        account_id=account_id,
        life_id=life_id,
    )

    async with postgres_sessions() as session:
        combat = PostgresCombatRepository(session)
        cultivation = PostgresCultivationRepository(session)
        assert await combat.insert_event_if_absent(event) is True
        credit = await cultivation.credit_combat_reward(
            life_id=life_id,
            kill_event_id=event.kill_event_id,
            amount=120,
            occurred_at=OCCURRED_AT,
        )
        await session.commit()

    assert credit.balance_after == 120
    assert credit.revision == 2

    async with postgres_sessions() as session:
        state = await session.get(LifeCultivationStateRow, life_id)
        entry = await session.scalar(
            select(CultivationResourceEntryRow).where(
                CultivationResourceEntryRow.kill_event_id == event.kill_event_id
            )
        )

    assert state is not None
    assert state.unrefined_cultivation == 120
    assert state.revision == 2
    assert entry is not None
    assert entry.delta_amount == 120
    assert entry.balance_after == 120


@pytest.mark.asyncio
async def test_repository_changes_roll_back_together(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    minecraft_uuid, account_id, life_id = await create_player_life(postgres_sessions)
    event = kill_event(
        minecraft_uuid=minecraft_uuid,
        account_id=account_id,
        life_id=life_id,
    )

    async with postgres_sessions() as session:
        combat = PostgresCombatRepository(session)
        cultivation = PostgresCultivationRepository(session)
        await combat.insert_event_if_absent(event)
        await combat.increment_mob_counter(life_id, "AzureWolf", OCCURRED_AT)
        await cultivation.credit_combat_reward(
            life_id=life_id,
            kill_event_id=event.kill_event_id,
            amount=120,
            occurred_at=OCCURRED_AT,
        )
        await session.rollback()

    async with postgres_sessions() as session:
        assert await session.get(CombatKillEventRow, event.kill_event_id) is None
        assert await session.get(LifeCultivationStateRow, life_id) is None
        assert (
            await session.scalar(
                select(LifeMobKillCounterRow).where(
                    LifeMobKillCounterRow.life_id == life_id,
                    LifeMobKillCounterRow.mob_internal_name == "AzureWolf",
                )
            )
            is None
        )
