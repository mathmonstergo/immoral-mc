from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import (
    LifeCultivationStateRow,
    LifeTechniqueRow,
    QuestCultivationRewardGrantRow,
    TechniqueLearnOperationRow,
)
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.db_models import ItemInstanceRow
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.db_models import QuestRewardGrantRow
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


@pytest.mark.asyncio
async def test_first_steps_reward_manual_can_be_learned_once(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        login = await client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_001)), "player_name": "RewardLoop"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        base = f"/api/v1/players/{account_id}/current-life"
        await client.put(
            f"{base}/quests/first-steps/accept",
            headers={"Idempotency-Key": str(UUID(int=9_002))},
            json={"provider_id": "old-man"},
        )
        await client.post(f"{base}/spirit-root")
        turn_in = await client.put(
            f"{base}/quests/first-steps/turn-in",
            headers={"Idempotency-Key": str(UUID(int=9_003))},
            json={"provider_id": "old-man", "inventory_item_instance_ids": []},
        )
        item_reward = turn_in.json()["rewards"][0]
        cultivation_reward = turn_in.json()["rewards"][1]
        item_instance_id = item_reward["item_instance_ids"][0]
        pending = await client.get(f"{base}/items/pending-deliveries")
        delivered = await client.put(
            f"{base}/items/{item_instance_id}/delivery-confirmation"
        )
        learn_headers = {"Idempotency-Key": str(UUID(int=9_004))}
        learned = await client.post(
            f"{base}/cultivation/techniques/learn",
            headers=learn_headers,
            json={"item_instance_id": item_instance_id},
        )
        replay = await client.post(
            f"{base}/cultivation/techniques/learn",
            headers=learn_headers,
            json={"item_instance_id": item_instance_id},
        )

    assert turn_in.status_code == 200
    assert cultivation_reward["applied_amount"] == 50
    assert cultivation_reward["pending_amount"] == 0
    assert pending.json()["items"][0]["item_instance_id"] == item_instance_id
    assert delivered.status_code == 200
    assert learned.status_code == 200
    assert replay.json() == learned.json()
    assert learned.json()["current_layer"] == 0

    async with postgres_sessions() as session:
        item = await session.get(ItemInstanceRow, UUID(item_instance_id))
        state = await session.get(LifeCultivationStateRow, life_id)
        technique_count = await session.scalar(
            select(func.count()).select_from(LifeTechniqueRow)
        )
        operation_count = await session.scalar(
            select(func.count()).select_from(TechniqueLearnOperationRow)
        )
        quest_grant_count = await session.scalar(
            select(func.count()).select_from(QuestRewardGrantRow)
        )
        cultivation_grant_count = await session.scalar(
            select(func.count()).select_from(QuestCultivationRewardGrantRow)
        )
    assert item is not None and item.status == "consumed"
    assert state is not None and state.unrefined_cultivation == 50
    assert technique_count == 1
    assert operation_count == 1
    assert quest_grant_count == 2
    assert cultivation_grant_count == 1


@pytest.mark.asyncio
async def test_reward_manual_round_trips_through_regional_storage(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        login = await client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_201)), "player_name": "StorageLoop"},
        )
        account_id = login.json()["account"]["account_id"]
        base = f"/api/v1/players/{account_id}/current-life"
        await client.put(
            f"{base}/quests/first-steps/accept",
            headers={"Idempotency-Key": str(UUID(int=9_202))},
            json={"provider_id": "old-man"},
        )
        await client.post(f"{base}/spirit-root")
        turn_in = await client.put(
            f"{base}/quests/first-steps/turn-in",
            headers={"Idempotency-Key": str(UUID(int=9_203))},
            json={"provider_id": "old-man", "inventory_item_instance_ids": []},
        )
        item_instance_id = turn_in.json()["rewards"][0]["item_instance_ids"][0]
        await client.put(f"{base}/items/{item_instance_id}/delivery-confirmation")

        area = "neutral_training_ground"
        empty = await client.get(f"{base}/storage/{area}?page=1")
        deposit_headers = {"Idempotency-Key": str(UUID(int=9_204))}
        deposit_body = {
            "move_kind": "deposit",
            "item_instance_id": item_instance_id,
            "expected_revision": 0,
            "source_page": None,
            "source_slot": None,
            "destination_page": 1,
            "destination_slot": 0,
            "view_page": 1,
        }
        deposited = await client.post(
            f"{base}/storage/{area}/moves",
            headers=deposit_headers,
            json=deposit_body,
        )
        replayed = await client.post(
            f"{base}/storage/{area}/moves",
            headers=deposit_headers,
            json=deposit_body,
        )
        other_area = await client.get(f"{base}/storage/accelerated_cave?page=1")
        withdrawn = await client.post(
            f"{base}/storage/{area}/moves",
            headers={"Idempotency-Key": str(UUID(int=9_205))},
            json={
                "move_kind": "withdraw",
                "item_instance_id": item_instance_id,
                "expected_revision": 1,
                "source_page": 1,
                "source_slot": 0,
                "destination_page": None,
                "destination_slot": None,
                "view_page": 1,
            },
        )
        inventory = await client.get(f"{base}/items/inventory")

    assert empty.json()["revision"] == 0
    assert deposited.status_code == 200
    assert deposited.content == replayed.content
    assert deposited.json()["snapshot"]["slots"][0]["item"]["location"] == "storage"
    assert other_area.json()["slots"] == []
    assert withdrawn.json()["snapshot"]["revision"] == 2
    assert withdrawn.json()["snapshot"]["slots"] == []
    assert inventory.json()["items"][0]["location"] == "inventory"


@pytest.mark.asyncio
async def test_full_reserve_reward_is_pending_and_claimable_after_capacity_returns(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with app_client(postgres_sessions) as client:
        login = await client.post(
            "/api/v1/players/login",
            json={"minecraft_uuid": str(UUID(int=9_101)), "player_name": "PendingReward"},
        )
        account_id = login.json()["account"]["account_id"]
        life_id = UUID(login.json()["current_life"]["life_id"])
        base = f"/api/v1/players/{account_id}/current-life"
        async with postgres_sessions() as session:
            session.add(
                LifeCultivationStateRow(
                    life_id=life_id,
                    current_level=1,
                    unrefined_cultivation=100,
                    realized_cultivation=0,
                    revision=1,
                )
            )
            await session.commit()
        await client.put(
            f"{base}/quests/first-steps/accept",
            headers={"Idempotency-Key": str(UUID(int=9_102))},
            json={"provider_id": "old-man"},
        )
        await client.post(f"{base}/spirit-root")
        turn_in = await client.put(
            f"{base}/quests/first-steps/turn-in",
            headers={"Idempotency-Key": str(UUID(int=9_103))},
            json={"provider_id": "old-man", "inventory_item_instance_ids": []},
        )
        reward = turn_in.json()["rewards"][1]
        async with postgres_sessions() as session:
            await session.execute(
                update(LifeCultivationStateRow)
                .where(LifeCultivationStateRow.life_id == life_id)
                .values(unrefined_cultivation=60)
            )
            await session.commit()
        claim_headers = {"Idempotency-Key": str(UUID(int=9_104))}
        claimed = await client.post(
            f"{base}/cultivation/quest-rewards/{reward['grant_id']}/claim",
            headers=claim_headers,
        )
        replay = await client.post(
            f"{base}/cultivation/quest-rewards/{reward['grant_id']}/claim",
            headers=claim_headers,
        )

    assert reward["applied_amount"] == 0
    assert reward["pending_amount"] == 50
    assert claimed.status_code == 200
    assert replay.json() == claimed.json()
    assert claimed.json()["applied_amount"] == 40
    assert claimed.json()["pending_amount"] == 10
    assert claimed.json()["unrefined_balance_after"] == 100
