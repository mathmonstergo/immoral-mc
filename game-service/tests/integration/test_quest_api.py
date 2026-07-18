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
from immortal_mmo.quest.definitions import QUEST_CATALOG
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository


def app_client(sessions: async_sessionmaker[AsyncSession]) -> httpx.AsyncClient:
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


async def login(client: httpx.AsyncClient, suffix: int = 1) -> dict:
    response = await client.post(
        "/api/v1/players/login",
        json={"minecraft_uuid": str(UUID(int=suffix)), "player_name": f"Quest{suffix}"},
    )
    return response.json()


@pytest.mark.asyncio
async def test_provider_catalog_and_interaction_read_contract(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        player = await login(client)
        account_id = player["account"]["account_id"]

        catalog = await client.get("/api/v1/quest-providers")
        state = await client.post(
            f"/api/v1/players/{account_id}/current-life/quest-interaction-state",
            json={"provider_ids": ["old-man", "old-man"]},
        )

    assert catalog.status_code == 200
    assert catalog.json()["revision"] == QUEST_CATALOG.revision
    assert catalog.json()["providers"][0]["provider_id"] == "old-man"
    assert state.status_code == 200
    assert state.json()["providers"][0]["quests"][0]["state"] == "available"
    assert state.json()["revision"] == {
        "player": 1,
        "quest": 0,
        "objectives": 0,
        "definitions": QUEST_CATALOG.revision,
    }


@pytest.mark.asyncio
async def test_full_quest_loop_returns_and_replays_frozen_http_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        player = await login(client, 2)
        account_id = player["account"]["account_id"]
        base = f"/api/v1/players/{account_id}/current-life/quests/first-steps"
        operation_id = str(UUID(int=200))

        accepted = await client.put(
            f"{base}/accept",
            headers={"Idempotency-Key": operation_id},
            json={"provider_id": "old-man"},
        )
        replayed = await client.put(
            f"{base}/accept",
            headers={"Idempotency-Key": operation_id},
            json={"provider_id": "old-man"},
        )
        await client.post(f"/api/v1/players/{account_id}/current-life/spirit-root")
        completed = await client.put(
            f"{base}/turn-in",
            headers={"Idempotency-Key": str(UUID(int=201))},
            json={"provider_id": "old-man"},
        )

    assert accepted.status_code == 200
    assert accepted.status_code == replayed.status_code
    assert accepted.content == replayed.content
    assert accepted.headers["content-type"] == replayed.headers["content-type"]
    assert accepted.json()["changed"] is True
    assert completed.json()["quest"]["state"] == "completed"


@pytest.mark.asyncio
async def test_committed_domain_failure_is_replayed_as_the_same_http_response(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        account_id = (await login(client, 3))["account"]["account_id"]
        path = f"/api/v1/players/{account_id}/current-life/quests/first-steps/turn-in"
        headers = {"Idempotency-Key": str(UUID(int=300))}
        body = {"provider_id": "old-man"}

        first = await client.put(path, headers=headers, json=body)
        replayed = await client.put(path, headers=headers, json=body)

    assert first.status_code == 409
    assert first.status_code == replayed.status_code
    assert first.content == replayed.content
    assert first.headers["content-type"] == replayed.headers["content-type"]
    assert first.json()["error"]["code"] == "quest.not_accepted"


@pytest.mark.asyncio
async def test_operation_id_reuse_with_a_different_fingerprint_conflicts(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        account_id = (await login(client, 4))["account"]["account_id"]
        operation_id = str(UUID(int=400))
        headers = {"Idempotency-Key": operation_id}
        await client.put(
            f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept",
            headers=headers,
            json={"provider_id": "old-man"},
        )

        conflict = await client.put(
            f"/api/v1/players/{account_id}/current-life/quests/first-steps/turn-in",
            headers=headers,
            json={"provider_id": "old-man"},
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "quest.idempotency_conflict"
