from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.catalog import (
    CombatRewardCatalog,
    LevelRewardCurve,
    MobRewardDefinition,
    RewardProfile,
)
from immortal_mmo.combat.db_models import CombatKillEventRow, LifeMobKillCounterRow
from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import (
    CultivationResourceEntryRow,
    LifeCultivationStateRow,
)
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.main import create_app
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository

KILLER_ID = UUID("33333333-3333-4333-8333-333333333333")
EVENT_ID = UUID("11111111-1111-5111-8111-111111111111")


def reward_catalog() -> CombatRewardCatalog:
    return CombatRewardCatalog(
        schema_version=1,
        curves=(LevelRewardCurve("linear-low", Decimal("1"), Decimal("100"), 2),),
        profiles=(RewardProfile("ordinary-wolf", 10, "linear-low"),),
        mobs=(MobRewardDefinition("AzureWolf", "ordinary-wolf", "compact"),),
    )


def client(sessions: async_sessionmaker[AsyncSession]) -> httpx.AsyncClient:
    app = create_app(
        uow_factory=SqlAlchemyUnitOfWorkFactory(
            sessions,
            PostgresPlayerRepository,
            PostgresQuestRepository,
            PostgresCombatRepository,
            PostgresCultivationRepository,
            PostgresItemRepository,
        ),
        combat_catalog=reward_catalog(),
    )
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def login(test_client: httpx.AsyncClient) -> dict:
    response = await test_client.post(
        "/api/v1/players/login",
        json={"minecraft_uuid": str(KILLER_ID), "player_name": "Combatant"},
    )
    assert response.status_code == 200
    return response.json()


def kill_payload(life_id: str, **overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "contract_version": 1,
        "event_id": str(EVENT_ID),
        "server_id": "main-1",
        "entity_uuid": "22222222-2222-4222-8222-222222222222",
        "mob_internal_name": "AzureWolf",
        "mob_level": "2.000",
        "killer_uuid": str(KILLER_ID),
        "source_life_id": life_id,
        "attribution_kind": "damage_over_time",
        "technique_id": "venom_mist",
        "cast_id": "55555555-5555-4555-8555-555555555555",
        "world": "minecraft:overworld",
        "x": 12.5,
        "y": 64.0,
        "z": -8.25,
        "occurred_at": "2026-07-15T12:00:00Z",
    }
    event.update(overrides)
    return {"contract_version": 1, "events": [event]}


@pytest.mark.asyncio
async def test_combat_batch_api_credits_and_replays_exactly_once(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with client(postgres_sessions) as test_client:
        player = await login(test_client)
        payload = kill_payload(player["current_life"]["life_id"])
        accepted = await test_client.post(
            "/api/v1/combat/mythicmob-kills/batch",
            json=payload,
        )
        duplicate = await test_client.post(
            "/api/v1/combat/mythicmob-kills/batch",
            json=payload,
        )

    assert accepted.status_code == 200
    assert accepted.json()["results"][0]["outcome"] == "accepted"
    assert accepted.json()["results"][0]["configured_reward_amount"] == 12
    assert accepted.json()["results"][0]["credited_cultivation_amount"] == 12
    assert duplicate.status_code == 200
    assert duplicate.json()["results"][0]["outcome"] == "duplicate"

    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(CombatKillEventRow)) == 1
        assert await session.scalar(select(func.count()).select_from(LifeMobKillCounterRow)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(CultivationResourceEntryRow)) == 1
        )
        state = await session.scalar(select(LifeCultivationStateRow))
    assert state is not None
    assert state.unrefined_cultivation == 12


@pytest.mark.asyncio
async def test_combat_batch_api_rejects_changed_replay_identity(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with client(postgres_sessions) as test_client:
        player = await login(test_client)
        life_id = player["current_life"]["life_id"]
        first = await test_client.post(
            "/api/v1/combat/mythicmob-kills/batch",
            json=kill_payload(life_id),
        )
        conflict = await test_client.post(
            "/api/v1/combat/mythicmob-kills/batch",
            json=kill_payload(life_id, technique_id="changed_technique"),
        )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "combat.kill_idempotency_conflict"


@pytest.mark.asyncio
async def test_full_reserve_reward_persists_accepted_zero_result_without_ledger_row(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    async with client(postgres_sessions) as test_client:
        player = await login(test_client)
        life_id = player["current_life"]["life_id"]
        async with postgres_sessions() as session:
            session.add(
                LifeCultivationStateRow(
                    life_id=UUID(life_id),
                    current_level=1,
                    unrefined_cultivation=100,
                    realized_cultivation=0,
                    revision=1,
                )
            )
            await session.commit()
        payload = kill_payload(life_id)
        accepted = await test_client.post("/api/v1/combat/mythicmob-kills/batch", json=payload)
        duplicate = await test_client.post("/api/v1/combat/mythicmob-kills/batch", json=payload)

    result = accepted.json()["results"][0]
    replay = duplicate.json()["results"][0]
    assert result["outcome"] == "accepted"
    assert result["configured_reward_amount"] == 12
    assert result["credited_cultivation_amount"] == 0
    assert result["unrefined_balance"] == 100
    assert replay["outcome"] == "duplicate"
    assert replay["credited_cultivation_amount"] == 0
    async with postgres_sessions() as session:
        ledger_count = await session.scalar(
            select(func.count()).select_from(CultivationResourceEntryRow)
        )
    assert ledger_count == 0
