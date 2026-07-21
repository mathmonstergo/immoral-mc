import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.models import CultivationState
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.definitions import QUEST_CATALOG
from immortal_mmo.quest.service import QuestService

NOW = datetime(2026, 7, 19, tzinfo=UTC)
CULTIVATION_ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"


async def _ready_first_steps() -> tuple[QuestService, FakeUnitOfWorkFactory, UUID, UUID]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    players = PlayerService(factory)
    login = await players.login(UUID(int=8_001), "Rewarded")
    service = QuestService(factory, clock=lambda: NOW)
    account_id = login.account.account_id
    await service.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=8_002),
        expected_life_id=login.current_life.life_id,
    )
    await players.detect_current_life_spirit_root(account_id)
    return service, factory, account_id, login.current_life.life_id


@pytest.mark.asyncio
async def test_turn_in_freezes_fixed_item_and_cultivation_rewards() -> None:
    service, factory, account_id, life_id = await _ready_first_steps()
    operation_id = UUID(int=8_003)

    first = await service.turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    replay = await QuestService(factory).turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )

    assert replay == first
    body = json.loads(first.body)
    assert body["rewards"] == [
        {
            "grant_id": body["rewards"][0]["grant_id"],
            "reward_id": "starter-technique-manual",
            "kind": "fixed_item",
            "status": "pending",
            "item_code": "technique_manual:GF_YinqiShu_01",
            "quantity": 1,
            "item_instance_ids": body["rewards"][0]["item_instance_ids"],
            "cultivation_amount": None,
            "applied_amount": 0,
            "pending_amount": 1,
        },
        {
            "grant_id": body["rewards"][1]["grant_id"],
            "reward_id": "starter-cultivation",
            "kind": "unrefined_cultivation",
            "status": "applied",
            "item_code": None,
            "quantity": None,
            "item_instance_ids": [],
            "cultivation_amount": 50,
            "applied_amount": 50,
            "pending_amount": 0,
        },
    ]
    assert factory.store._state.cultivation_states[life_id].unrefined_cultivation == 50
    assert len(factory.store._state.item_instances) == 1


@pytest.mark.asyncio
async def test_full_reserve_keeps_cultivation_reward_pending_without_loss() -> None:
    service, factory, account_id, life_id = await _ready_first_steps()
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        1,
        100,
        0,
        None,
        1,
    )

    response = await service.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=8_004),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )

    reward = json.loads(response.body)["rewards"][1]
    assert reward["status"] == "pending"
    assert reward["applied_amount"] == 0
    assert reward["pending_amount"] == 50
    assert factory.store._state.cultivation_states[life_id].unrefined_cultivation == 100


@pytest.mark.asyncio
async def test_pending_cultivation_reward_claim_is_idempotent() -> None:
    service, factory, account_id, life_id = await _ready_first_steps()
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        1,
        100,
        0,
        None,
        1,
    )
    turn_in = await service.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=8_005),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    grant_id = UUID(json.loads(turn_in.body)["rewards"][1]["grant_id"])
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        1,
        60,
        0,
        None,
        1,
    )

    cultivation = CultivationService(
        factory,
        load_realm_catalog(CULTIVATION_ROOT / "realm_catalog.json"),
        clock=lambda: NOW,
    )
    first = await cultivation.claim_pending_quest_reward(
        account_id=account_id,
        grant_id=grant_id,
        idempotency_key=UUID(int=8_006),
    )
    replay = await cultivation.claim_pending_quest_reward(
        account_id=account_id,
        grant_id=grant_id,
        idempotency_key=UUID(int=8_006),
    )

    assert replay == first
    assert first.applied_amount == 40
    assert first.pending_amount == 10
    stored = next(
        grant
        for grant in factory.store._state.quest_reward_grants.values()
        if grant.grant_id == grant_id
    )
    assert stored.applied_amount == 40
    assert stored.pending_amount == 10


def test_reward_values_are_fixed_content_not_player_context() -> None:
    definition = QUEST_CATALOG.get_quest("first-steps")
    assert tuple(reward.reward_id for reward in definition.rewards) == (
        "starter-technique-manual",
        "starter-cultivation",
    )
    assert definition.rewards[1].amount == 50
