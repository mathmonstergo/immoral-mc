from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from tests.support.fakes import NoOpQuestRepository

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.player.db_models import (
    AccountMinecraftNameRow,
    AccountRow,
    LifeRow,
    LifeSpiritRootRow,
)
from immortal_mmo.player.models import SpiritRootGenerator
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.player.service import PlayerLifecycleError, PlayerService


def player_service(
    sessions: async_sessionmaker[AsyncSession],
    *,
    generator: SpiritRootGenerator | None = None,
) -> PlayerService:
    return PlayerService(
        SqlAlchemyUnitOfWorkFactory(
            sessions,
            PostgresPlayerRepository,
            NoOpQuestRepository,
            PostgresCombatRepository,
            PostgresCultivationRepository,
            PostgresItemRepository,
        ),
        spirit_root_generator=generator,
    )


@pytest.mark.asyncio
async def test_concurrent_first_login_creates_one_account_and_one_alive_life(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    service = player_service(postgres_sessions)
    minecraft_uuid = uuid4()

    first, second = await asyncio.gather(
        service.login(minecraft_uuid, "Concurrent"),
        service.login(minecraft_uuid, "Concurrent"),
    )

    assert first.account == second.account
    assert first.current_life == second.current_life
    async with postgres_sessions() as session:
        account_count = await session.scalar(select(func.count()).select_from(AccountRow))
        alive_count = await session.scalar(
            select(func.count()).select_from(LifeRow).where(LifeRow.status == "alive")
        )
    assert account_count == 1
    assert alive_count == 1


@pytest.mark.asyncio
async def test_account_upsert_tracks_casing_history_and_revision_exactly_once(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    service = player_service(postgres_sessions)
    minecraft_uuid = uuid4()
    first = await service.login(minecraft_uuid, "Steve")
    async with postgres_sessions() as session:
        initial = (
            await session.execute(
                select(AccountRow).where(AccountRow.account_id == first.account.account_id)
            )
        ).scalar_one()
        initial_updated_at = initial.updated_at
        initial_last_seen_at = initial.last_seen_at
        initial_first_seen_at = await session.scalar(
            select(AccountMinecraftNameRow.first_seen_at).where(
                AccountMinecraftNameRow.account_id == first.account.account_id
            )
        )

    changed = await service.login(minecraft_uuid, "steve")
    async with postgres_sessions() as session:
        changed_revision = await session.scalar(
            select(AccountRow.revision).where(AccountRow.account_id == first.account.account_id)
        )
    repeated = await service.login(minecraft_uuid, "steve")

    assert changed.account.player_name == "steve"
    assert repeated.account.player_name == "steve"
    async with postgres_sessions() as session:
        account = (
            await session.execute(
                select(AccountRow).where(AccountRow.account_id == first.account.account_id)
            )
        ).scalar_one()
        observations = (
            await session.execute(
                select(AccountMinecraftNameRow).where(
                    AccountMinecraftNameRow.account_id == first.account.account_id
                )
            )
        ).scalars().all()
    assert account.updated_at > initial_updated_at
    assert account.last_seen_at > initial_last_seen_at
    assert changed_revision == 2
    assert account.revision == 2
    assert len(observations) == 1
    assert observations[0].normalized_name == "steve"
    assert observations[0].player_name == "steve"
    assert observations[0].first_seen_at == initial_first_seen_at
    assert observations[0].first_seen_at <= observations[0].last_seen_at


@pytest.mark.asyncio
async def test_name_history_is_per_account_and_survives_new_service_sessions(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    first_service = player_service(postgres_sessions)
    first = await first_service.login(UUID(int=1), "SharedName")
    await first_service.login(UUID(int=1), "Renamed")
    second = await first_service.login(UUID(int=2), "SharedName")

    restarted_service = player_service(postgres_sessions)
    restarted = await restarted_service.login(UUID(int=1), "Renamed")

    assert restarted.account.account_id == first.account.account_id
    assert restarted.current_life.life_id == first.current_life.life_id
    assert second.account.account_id != first.account.account_id
    async with postgres_sessions() as session:
        observations = (
            await session.execute(
                select(AccountMinecraftNameRow).order_by(
                    AccountMinecraftNameRow.account_id,
                    AccountMinecraftNameRow.normalized_name,
                )
            )
        ).scalars().all()
    assert len(observations) == 3
    assert [row.normalized_name for row in observations].count("sharedname") == 2


@pytest.mark.asyncio
async def test_login_rejects_historical_account_without_alive_life(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    service = player_service(postgres_sessions)
    minecraft_uuid = uuid4()
    login = await service.login(minecraft_uuid, "History")
    async with postgres_sessions.begin() as session:
        await session.execute(
            update(LifeRow)
            .where(LifeRow.life_id == login.current_life.life_id)
            .values(
                status="reincarnated",
                died_at=datetime.now(UTC),
                death_cause_code="test_reincarnation",
            )
        )

    with pytest.raises(PlayerLifecycleError):
        await service.login(minecraft_uuid, "History")

    async with postgres_sessions() as session:
        lives = (
            await session.execute(
                select(LifeRow).where(LifeRow.account_id == login.account.account_id)
            )
        ).scalars().all()
    assert len(lives) == 1
    assert lives[0].status == "reincarnated"


@pytest.mark.asyncio
async def test_database_rejects_second_alive_life_through_repository(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        NoOpQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    async with factory() as uow:
        account = await uow.players.upsert_account(uuid4(), "DoubleLife")
        await uow.commit()
    async with postgres_sessions.begin() as session:
        session.add(
            LifeRow(
                life_id=uuid4(),
                account_id=account.account_id,
                generation_no=2,
                status="alive",
            )
        )

    with pytest.raises(IntegrityError) as caught:
        async with factory() as uow:
            await uow.players.insert_first_life(account.account_id)
            await uow.commit()

    assert caught.value.orig.sqlstate == "23505"
    assert caught.value.orig.__cause__.constraint_name == "ux_lives_one_alive_per_account"


@pytest.mark.asyncio
async def test_concurrent_root_detection_is_single_revisioned_and_restart_safe(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    generator = SpiritRootGenerator(
        roll=lambda: 0.95,
        choose_base_elements=lambda count: ("metal", "wood", "water", "fire", "earth")[:count],
        choose_variant_pair=lambda: ("metal", "thunder"),
    )
    service = player_service(postgres_sessions, generator=generator)
    login = await service.login(uuid4(), "Rooted")

    first, second = await asyncio.gather(
        service.detect_current_life_spirit_root(login.account.account_id),
        service.detect_current_life_spirit_root(login.account.account_id),
    )

    assert first.spirit_root == second.spirit_root
    assert sorted([first.already_detected, second.already_detected]) == [False, True]
    restarted = player_service(postgres_sessions, generator=generator)
    facts = await restarted.get_current_life_facts(login.account.account_id)
    repeated = await restarted.detect_current_life_spirit_root(login.account.account_id)
    assert repeated.already_detected is True
    assert repeated.spirit_root == first.spirit_root
    assert facts.spirit_root is not None
    assert facts.spirit_root.quality_code == "variant"
    assert facts.spirit_root.base_element_codes == ("metal",)
    assert facts.spirit_root.variant_element_code == "thunder"
    assert facts.revision == 2
    async with postgres_sessions() as session:
        root_count = await session.scalar(select(func.count()).select_from(LifeSpiritRootRow))
        life_revision = await session.scalar(
            select(LifeRow.revision).where(LifeRow.life_id == login.current_life.life_id)
        )
    assert root_count == 1
    assert life_revision == 2
