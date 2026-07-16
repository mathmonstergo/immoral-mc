from uuid import UUID

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
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
