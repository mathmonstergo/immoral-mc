from uuid import UUID

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.db_models import LifeRow
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.db_models import QuestOperationRow, QuestProgressRow
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
    assert catalog.json()["contract_version"] == 1
    assert catalog.json()["revision"] == QUEST_CATALOG.revision
    assert catalog.json()["providers"][0]["provider_id"] == "old-man"
    assert state.status_code == 200
    assert state.json()["contract_version"] == 2
    assert state.json()["providers"][0]["quests"][0]["state"] == "available"
    quest = state.json()["providers"][0]["quests"][0]
    assert quest["description"] == "完成灵根检测，踏出修行之路的第一步。"
    assert quest["objectives"][0]["objective_type"] == "current_life_spirit_root_present"
    assert quest["objectives"][0]["item_code"] is None
    assert [reward["kind"] for reward in quest["reward_previews"]] == [
        "fixed_item",
        "unrefined_cultivation",
    ]
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
        life_id = player["current_life"]["life_id"]
        base = f"/api/v1/players/{account_id}/current-life/quests/first-steps"
        operation_id = str(UUID(int=200))

        accepted = await client.put(
            f"{base}/accept",
            headers={"Idempotency-Key": operation_id},
            json={"provider_id": "old-man", "expected_life_id": life_id},
        )
        replayed = await client.put(
            f"{base}/accept",
            headers={"Idempotency-Key": operation_id},
            json={"provider_id": "old-man", "expected_life_id": life_id},
        )
        await client.post(f"/api/v1/players/{account_id}/current-life/spirit-root")
        completed = await client.put(
            f"{base}/turn-in",
            headers={"Idempotency-Key": str(UUID(int=201))},
            json={
                "provider_id": "old-man",
                "expected_life_id": life_id,
                "inventory_item_instance_ids": [],
            },
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
        player = await login(client, 3)
        account_id = player["account"]["account_id"]
        life_id = player["current_life"]["life_id"]
        path = f"/api/v1/players/{account_id}/current-life/quests/first-steps/turn-in"
        headers = {"Idempotency-Key": str(UUID(int=300))}
        body = {
            "provider_id": "old-man",
            "expected_life_id": life_id,
            "inventory_item_instance_ids": [],
        }

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
        player = await login(client, 4)
        account_id = player["account"]["account_id"]
        life_id = player["current_life"]["life_id"]
        operation_id = str(UUID(int=400))
        headers = {"Idempotency-Key": operation_id}
        await client.put(
            f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept",
            headers=headers,
            json={"provider_id": "old-man", "expected_life_id": life_id},
        )

        conflict = await client.put(
            f"/api/v1/players/{account_id}/current-life/quests/first-steps/turn-in",
            headers=headers,
            json={
                "provider_id": "old-man",
                "expected_life_id": life_id,
                "inventory_item_instance_ids": [],
            },
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "quest.idempotency_conflict"


@pytest.mark.asyncio
async def test_stale_life_mutation_is_rejected_before_writing_new_life(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        player = await login(client, 5)
        account_id = player["account"]["account_id"]
        old_life_id = UUID(player["current_life"]["life_id"])
        new_life_id = UUID(int=5_001)
        async with postgres_sessions.begin() as session:
            await session.execute(
                text(
                    """
                    UPDATE lives
                    SET status = 'reincarnated', died_at = now(),
                        death_cause_code = 'test_reincarnation'
                    WHERE life_id = :life_id
                    """
                ),
                {"life_id": old_life_id},
            )
            session.add(
                LifeRow(
                    life_id=new_life_id,
                    account_id=UUID(account_id),
                    generation_no=2,
                    status="alive",
                )
            )

        stale_operation_id = UUID(int=500)
        path = f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept"
        stale = await client.put(
            path,
            headers={"Idempotency-Key": str(stale_operation_id)},
            json={
                "provider_id": "old-man",
                "expected_life_id": str(old_life_id),
            },
        )
        fresh = await client.put(
            path,
            headers={"Idempotency-Key": str(UUID(int=501))},
            json={
                "provider_id": "old-man",
                "expected_life_id": str(new_life_id),
            },
        )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "quest.stale_life"
    assert stale.json()["error"]["retryable"] is False
    assert fresh.status_code == 200
    assert fresh.json()["interaction_state"]["life_id"] == str(new_life_id)
    async with postgres_sessions() as session:
        assert await session.get(QuestOperationRow, stale_operation_id) is None
        progress = await session.get(QuestProgressRow, (new_life_id, "first-steps"))
    assert progress is not None and progress.status == "active"
