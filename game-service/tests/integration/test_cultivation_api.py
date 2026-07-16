from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import (
    CultivationSessionRow,
    CultivationSessionTechniqueRow,
    LifeTechniqueRow,
)
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository


def client(sessions: async_sessionmaker[AsyncSession]) -> httpx.AsyncClient:
    app = create_app(
        uow_factory=SqlAlchemyUnitOfWorkFactory(
            sessions,
            PostgresPlayerRepository,
            PostgresQuestRepository,
            PostgresCombatRepository,
            PostgresCultivationRepository,
            PostgresItemRepository,
        )
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_new_current_life_has_level_one_empty_cultivation_snapshot(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    account_id = UUID(int=500)
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={
                "minecraft_uuid": str(account_id),
                "player_name": "Cultivator",
            },
        )
        stored_account_id = login.json()["account"]["account_id"]
        response = await test_client.get(
            f"/api/v1/players/{stored_account_id}/current-life/cultivation"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["current_level"] == 1
    assert body["realm_name"] == "练气一层"
    assert body["current_progress"] == 0
    assert body["max_exp"] == 100
    assert body["unrefined_reserve"] == 0
    assert body["reserve_cap"] == 100


@pytest.mark.asyncio
async def test_start_seclusion_persists_unordered_authoritative_selection(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    technique_ids = (UUID(int=902), UUID(int=901))
    async with client(postgres_sessions) as test_client:
        login = await test_client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=501)), "player_name": "Retreater"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = login.json()["current_life"]["life_id"]
        async with postgres_sessions() as session:
            for index, technique_id in enumerate(technique_ids):
                session.add(
                    LifeTechniqueRow(
                        life_technique_id=technique_id,
                        life_id=UUID(life_id),
                        technique_id=f"GF_Test_{index}",
                        definition_version=1,
                        group_code="qi",
                        major_realm="练气",
                        invested_amount=0,
                        max_investment=100,
                        current_layer=1,
                        status="active",
                    )
                )
            await session.commit()
        response = await test_client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/seclusions",
            headers={"Idempotency-Key": str(UUID(int=999))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(value) for value in technique_ids],
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    async with postgres_sessions() as session:
        session_count = await session.scalar(
            select(func.count()).select_from(CultivationSessionRow)
        )
        selections = (
            await session.scalars(
                select(CultivationSessionTechniqueRow.life_technique_id).order_by(
                    CultivationSessionTechniqueRow.life_technique_id
                )
            )
        ).all()
    assert session_count == 1
    assert tuple(selections) == tuple(sorted(technique_ids))
