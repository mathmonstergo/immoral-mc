from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.schemas import LearnTechniqueRequest
from immortal_mmo.cultivation.service import (
    CultivationService,
    CultivationTechniqueLearnConflictError,
)
from immortal_mmo.item.models import ItemInstance, ItemInstanceStatus
from immortal_mmo.player.service import PlayerService

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"
NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_learn_request_rejects_client_supplied_technique_identity() -> None:
    with pytest.raises(ValidationError):
        LearnTechniqueRequest.model_validate(
            {
                "item_instance_id": str(UUID(int=8_100)),
                "technique_id": "GF_YinqiShu_01",
            }
        )


@pytest.mark.asyncio
async def test_manual_learns_layer_zero_technique_and_replays() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    players = PlayerService(factory)
    login = await players.login(UUID(int=8_101), "Learner")
    await players.detect_current_life_spirit_root(login.account.account_id)
    life_id = login.current_life.life_id
    item_instance_id = UUID(int=8_102)
    issuance_id = UUID(int=8_103)
    factory.store._state.item_instances[item_instance_id] = ItemInstance(
        item_instance_id=item_instance_id,
        life_id=life_id,
        item_code="technique_manual:GF_YinqiShu_01",
        definition_version=1,
        technique_id="GF_YinqiShu_01",
        issuance_id=issuance_id,
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.PENDING_DELIVERY,
        created_at=NOW,
        delivered_at=None,
        consumed_at=None,
    )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        clock=lambda: NOW,
    )
    async with factory() as uow:
        await uow.items.confirm_delivery(
            item_instance_id=item_instance_id,
            life_id=life_id,
            delivered_at=NOW,
        )
        await uow.commit()
    operation_id = UUID(int=8_104)

    learned = await service.learn_technique(
        account_id=login.account.account_id,
        item_instance_id=item_instance_id,
        idempotency_key=operation_id,
    )
    replay = await service.learn_technique(
        account_id=login.account.account_id,
        item_instance_id=item_instance_id,
        idempotency_key=operation_id,
    )

    assert replay == learned
    assert learned.current_layer == 0
    stored = factory.store._state.life_techniques[learned.life_technique_id]
    assert stored.invested_amount == 0
    assert stored.max_investment == 3_780
    assert stored.status == "active"
    assert (
        factory.store._state.item_instances[item_instance_id].status
        is ItemInstanceStatus.CONSUMED
    )


@pytest.mark.asyncio
async def test_learn_idempotency_key_reuse_with_changed_item_conflicts() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    players = PlayerService(factory)
    login = await players.login(UUID(int=8_111), "LearnerConflict")
    await players.detect_current_life_spirit_root(login.account.account_id)
    life_id = login.current_life.life_id
    first_id = UUID(int=8_112)
    second_id = UUID(int=8_113)
    for item_id in (first_id, second_id):
        factory.store._state.item_instances[item_id] = ItemInstance(
            item_instance_id=item_id,
            life_id=life_id,
            item_code="technique_manual:GF_YinqiShu_01",
            definition_version=1,
            technique_id="GF_YinqiShu_01",
            issuance_id=UUID(int=item_id.int + 100),
            issuance_ordinal=0,
            quest_reward_grant_id=None,
            status=ItemInstanceStatus.PENDING_DELIVERY,
            created_at=NOW,
            delivered_at=None,
            consumed_at=None,
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        clock=lambda: NOW,
    )
    async with factory() as uow:
        await uow.items.confirm_delivery(
            item_instance_id=first_id,
            life_id=life_id,
            delivered_at=NOW,
        )
        await uow.items.confirm_delivery(
            item_instance_id=second_id,
            life_id=life_id,
            delivered_at=NOW,
        )
        await uow.commit()
    operation_id = UUID(int=8_114)
    await service.learn_technique(
        account_id=login.account.account_id,
        item_instance_id=first_id,
        idempotency_key=operation_id,
    )

    with pytest.raises(CultivationTechniqueLearnConflictError):
        await service.learn_technique(
            account_id=login.account.account_id,
            item_instance_id=second_id,
            idempotency_key=operation_id,
        )
