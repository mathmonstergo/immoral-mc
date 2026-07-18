from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.cultivation.db_models import (
    CultivationResourceEntryRow,
    LifeCultivationStateRow,
    LifeRealmEntryRow,
    LifeTechniqueRow,
    TechniqueInvestmentEntryRow,
)
from immortal_mmo.cultivation.models import (
    CultivationSession,
    TechniqueInvestmentChange,
)
from immortal_mmo.cultivation.postgres_repository import (
    ActiveCultivationSessionExists,
    PostgresCultivationRepository,
)
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository


async def create_life(sessions: async_sessionmaker[AsyncSession]) -> UUID:
    async with sessions() as session:
        players = PostgresPlayerRepository(session)
        account = await players.upsert_account(uuid4(), "Cultivator")
        life = await players.insert_first_life(account.account_id)
        await session.commit()
        return life.life_id


@pytest.mark.asyncio
async def test_default_state_creation_and_sorted_technique_locking(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    first_id, second_id = sorted((uuid4(), uuid4()), key=lambda value: value.int)

    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        state = await repository.get_or_create_state(life_id, for_update=True)
        session.add_all(
            [
                LifeTechniqueRow(
                    life_technique_id=second_id,
                    life_id=life_id,
                    technique_id="GF_Ice_02",
                    definition_version=1,
                    group_code="qi",
                    major_realm="练气",
                    invested_amount=0,
                    max_investment=100,
                    current_layer=1,
                    status="active",
                ),
                LifeTechniqueRow(
                    life_technique_id=first_id,
                    life_id=life_id,
                    technique_id="GF_Fire_01",
                    definition_version=1,
                    group_code="qi",
                    major_realm="练气",
                    invested_amount=0,
                    max_investment=100,
                    current_layer=1,
                    status="active",
                ),
            ]
        )
        await session.flush()
        techniques = await repository.get_techniques(
            life_id,
            (second_id, first_id),
            for_update=True,
        )
        await session.rollback()

    assert state.current_level == 1
    assert state.unrefined_cultivation == 0
    assert state.realized_cultivation == 0
    assert tuple(item.life_technique_id for item in techniques) == (first_id, second_id)


@pytest.mark.asyncio
async def test_active_realm_chain_ignores_invalidated_history(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        await repository.get_or_create_state(life_id, for_update=False)
        active_id = uuid4()
        invalidated_id = uuid4()
        session.add_all(
            [
                LifeRealmEntryRow(
                    realm_entry_id=active_id,
                    life_id=life_id,
                    generation=1,
                    parent_entry_id=None,
                    source_level=1,
                    target_level=2,
                    source_group="qi",
                    target_group="qi",
                    source_floor=100,
                    target_baseline=100,
                    transition_kind="adjacent",
                    transition_session_id=None,
                    status="active",
                    invalidated_at=None,
                ),
                LifeRealmEntryRow(
                    realm_entry_id=invalidated_id,
                    life_id=life_id,
                    generation=2,
                    parent_entry_id=active_id,
                    source_level=2,
                    target_level=3,
                    source_group="qi",
                    target_group="qi",
                    source_floor=250,
                    target_baseline=250,
                    transition_kind="adjacent",
                    transition_session_id=None,
                    status="invalidated",
                    invalidated_at=now,
                ),
            ]
        )
        await session.flush()
        chain = await repository.get_active_realm_chain(life_id, for_update=False)
        await session.rollback()

    assert tuple(entry.realm_entry_id for entry in chain) == (active_id,)


@pytest.mark.asyncio
async def test_open_session_exclusivity_is_translated_to_domain_conflict(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)

    def ordinary_session() -> CultivationSession:
        return CultivationSession(
            session_id=uuid4(),
            life_id=life_id,
            session_kind="ordinary",
            status="active",
            idempotency_key=uuid4(),
            request_fingerprint="a" * 64,
            area_id="neutral_training_ground",
            content_version="v1",
            source_level=1,
            target_level=None,
            frozen_snapshot={},
            cumulative_elapsed_seconds=0,
            cumulative_generated=0,
            cumulative_reserve_consumed=0,
            cumulative_retained=0,
            started_at=now,
            completes_at=now + timedelta(hours=1),
            settled_at=None,
            revision=1,
        )

    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        await repository.get_or_create_state(life_id, for_update=True)
        await repository.insert_session(ordinary_session())
        with pytest.raises(ActiveCultivationSessionExists):
            await repository.insert_session(ordinary_session())
        await session.rollback()


@pytest.mark.asyncio
async def test_technique_ledger_and_realized_aggregate_update_atomically(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    technique_id = uuid4()
    operation_id = uuid4()
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        await repository.get_or_create_state(life_id, for_update=True)
        session.add(
            LifeTechniqueRow(
                life_technique_id=technique_id,
                life_id=life_id,
                technique_id="GF_Fire_01",
                definition_version=1,
                group_code="qi",
                major_realm="练气",
                invested_amount=0,
                max_investment=3_765,
                current_layer=1,
                status="active",
            )
        )
        await session.flush()
        state = await repository.apply_technique_investments(
            life_id=life_id,
            operation_id=operation_id,
            session_id=None,
            changes=(
                TechniqueInvestmentChange(technique_id, 3_765, "seclusion_realization"),
            ),
            occurred_at=now,
        )
        await session.commit()

    async with postgres_sessions() as session:
        technique_values = (
            await session.execute(
                select(
                    LifeTechniqueRow.invested_amount,
                    LifeTechniqueRow.current_layer,
                ).where(LifeTechniqueRow.life_technique_id == technique_id)
            )
        ).one()
        investment_count = len((await session.scalars(select(TechniqueInvestmentEntryRow))).all())
        resource_count = len((await session.scalars(select(CultivationResourceEntryRow))).all())
        stored_state = await session.get(LifeCultivationStateRow, life_id)

    assert state.realized_cultivation == 3_765
    assert technique_values.invested_amount == 3_765
    assert technique_values.current_layer == 13
    assert stored_state is not None and stored_state.realized_cultivation == 3_765
    assert investment_count == 1
    assert resource_count == 1


@pytest.mark.asyncio
async def test_negative_investment_persists_reduced_current_layer(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    technique_id = uuid4()
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        await repository.get_or_create_state(life_id, for_update=True)
        session.add(
            LifeTechniqueRow(
                life_technique_id=technique_id,
                life_id=life_id,
                technique_id="GF_Fire_01",
                definition_version=1,
                group_code="qi",
                major_realm="练气",
                invested_amount=0,
                max_investment=3_765,
                current_layer=1,
                status="active",
            )
        )
        await session.flush()
        await repository.apply_technique_investments(
            life_id=life_id,
            operation_id=uuid4(),
            session_id=None,
            changes=(
                TechniqueInvestmentChange(technique_id, 3_765, "seclusion_realization"),
            ),
            occurred_at=now,
        )
        await session.commit()

    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        state = await repository.apply_technique_investments(
            life_id=life_id,
            operation_id=uuid4(),
            session_id=None,
            changes=(TechniqueInvestmentChange(technique_id, -3_765, "abandonment"),),
            occurred_at=now + timedelta(seconds=1),
        )
        await session.commit()

    async with postgres_sessions() as session:
        technique_values = (
            await session.execute(
                select(
                    LifeTechniqueRow.invested_amount,
                    LifeTechniqueRow.current_layer,
                ).where(LifeTechniqueRow.life_technique_id == technique_id)
            )
        ).one()
        investment_count = len((await session.scalars(select(TechniqueInvestmentEntryRow))).all())
        stored_state = await session.get(LifeCultivationStateRow, life_id)

    assert state.realized_cultivation == 0
    assert technique_values.invested_amount == 0
    assert technique_values.current_layer == 1
    assert stored_state is not None and stored_state.realized_cultivation == 0
    assert investment_count == 2


@pytest.mark.asyncio
async def test_invalid_investment_batch_leaves_every_balance_unchanged(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    life_id = await create_life(postgres_sessions)
    first_id, second_id = UUID(int=1), UUID(int=2)
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    async with postgres_sessions() as session:
        repository = PostgresCultivationRepository(session)
        await repository.get_or_create_state(life_id, for_update=True)
        for life_technique_id, technique_code in (
            (first_id, "GF_Fire_01"),
            (second_id, "GF_Ice_02"),
        ):
            session.add(
                LifeTechniqueRow(
                    life_technique_id=life_technique_id,
                    life_id=life_id,
                    technique_id=technique_code,
                    definition_version=1,
                    group_code="qi",
                    major_realm="练气",
                    invested_amount=0,
                    max_investment=3_765,
                    current_layer=1,
                    status="active",
                )
            )
        await session.flush()
        with pytest.raises(ValueError, match="exceeds its bounds"):
            await repository.apply_technique_investments(
                life_id=life_id,
                operation_id=uuid4(),
                session_id=None,
                changes=(
                    TechniqueInvestmentChange(first_id, 10, "seclusion_realization"),
                    TechniqueInvestmentChange(second_id, 3_766, "seclusion_realization"),
                ),
                occurred_at=now,
            )
        await session.commit()

    async with postgres_sessions() as session:
        balances = tuple(
            await session.scalars(
                select(LifeTechniqueRow.invested_amount).order_by(
                    LifeTechniqueRow.life_technique_id
                )
            )
        )
        state = await session.get(LifeCultivationStateRow, life_id)
        ledger_count = len((await session.scalars(select(TechniqueInvestmentEntryRow))).all())

    assert balances == (0, 0)
    assert state is not None and state.realized_cultivation == 0
    assert ledger_count == 0
