from uuid import UUID

import httpx
import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.models import CultivationState, LifeTechnique, RealmEntry
from immortal_mmo.main import create_app
from immortal_mmo.player.models import SpiritRoot


async def logged_in_client() -> tuple[httpx.AsyncClient, FakeStore, str, UUID]:
    store = FakeStore()
    app = create_app(uow_factory=FakeUnitOfWorkFactory(store))
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )
    login = await client.post(
        "/api/v1/players/login",
        json={"minecraft_uuid": str(UUID(int=30_001)), "player_name": "ApiErrors"},
    )
    return (
        client,
        store,
        login.json()["account"]["account_id"],
        UUID(login.json()["current_life"]["life_id"]),
    )


@pytest.mark.asyncio
async def test_seclusion_api_serializes_rule_conflict_and_not_found_errors() -> None:
    client, store, account_id, life_id = await logged_in_client()
    technique_id = UUID(int=30_002)
    store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "GF_Api_Error",
        1,
        "qi",
        "练气",
        0,
        100,
        1,
        "active",
    )
    path = f"/api/v1/players/{account_id}/current-life/cultivation/seclusions"
    try:
        rule = await client.post(
            path,
            headers={"Idempotency-Key": str(UUID(int=30_003))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(technique_id), str(technique_id)],
            },
        )
        started = await client.post(
            path,
            headers={"Idempotency-Key": str(UUID(int=30_004))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(technique_id)],
            },
        )
        conflict = await client.post(
            path,
            headers={"Idempotency-Key": str(UUID(int=30_005))},
            json={
                "area_id": "neutral_training_ground",
                "technique_ids": [str(technique_id)],
            },
        )
        missing = await client.get(f"{path}/{UUID(int=30_006)}")
    finally:
        await client.aclose()

    assert rule.status_code == 409
    assert rule.json()["error"]["code"] == "cultivation.seclusion_rule_violation"
    assert started.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "cultivation.seclusion_conflict"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "cultivation.seclusion_not_found"


@pytest.mark.asyncio
async def test_breakthrough_api_serializes_item_shortage_without_state_changes() -> None:
    client, store, account_id, life_id = await logged_in_client()
    technique_id = UUID(int=30_102)
    entry_id = UUID(int=30_103)
    store._state.spirit_roots[life_id] = SpiritRoot(
        life_id,
        "triple",
        ("metal", "wood", "water"),
        None,
        1,
    )
    store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "GF_Api_Breakthrough",
        1,
        "qi",
        "练气",
        11_343,
        20_000,
        13,
        "active",
    )
    store._state.realm_entries[entry_id] = RealmEntry(
        entry_id,
        life_id,
        1,
        None,
        9,
        10,
        "qi",
        "qi",
        7_514,
        7_514,
        "adjacent",
        None,
        "active",
        None,
    )
    store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        10,
        0,
        11_343,
        None,
        1,
    )
    try:
        response = await client.post(
            f"/api/v1/players/{account_id}/current-life/cultivation/breakthroughs",
            headers={"Idempotency-Key": str(UUID(int=30_104))},
            json={"pill_count": 1},
        )
    finally:
        await client.aclose()

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "item.insufficient_quantity"
    assert store._state.cultivation_states[life_id].active_session_id is None
    assert store._state.cultivation_sessions == {}
    assert store._state.breakthrough_debits == {}
    assert store._state.item_entries == {}
