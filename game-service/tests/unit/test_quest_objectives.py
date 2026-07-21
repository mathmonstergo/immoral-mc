import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.models import (
    CultivationState,
    LifeTechnique,
    TechniqueInvestmentChange,
)
from immortal_mmo.item.models import ItemInstance, ItemInstanceStatus, ItemLocation
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestObjectiveDefinition,
    QuestProviderDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)
from immortal_mmo.quest.progression import QuestEventProgressionService
from immortal_mmo.quest.service import QuestService

NOW = datetime(2026, 7, 18, 8, tzinfo=UTC)


def typed_catalog(*objectives: QuestObjectiveDefinition) -> QuestDefinitionCatalog:
    quest = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        quest_id="typed-objectives",
        objectives=tuple(objectives),
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    return QuestDefinitionCatalog(quests=(quest,), providers=(provider,))


async def setup_services(
    catalog: QuestDefinitionCatalog,
) -> tuple[QuestService, FakeUnitOfWorkFactory, UUID, UUID]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=18_001), "ObjectiveTester")
    return (
        QuestService(factory, catalog, clock=lambda: NOW),
        factory,
        login.account.account_id,
        login.current_life.life_id,
    )


def response_body(response) -> dict:
    return json.loads(response.body)


def grant_inventory_items(
    factory: FakeUnitOfWorkFactory,
    life_id: UUID,
    item_code: str,
    quantity: int,
    base_id: int,
) -> tuple[UUID, ...]:
    identities = tuple(UUID(int=base_id + offset) for offset in range(quantity))
    for offset, item_id in enumerate(identities):
        factory.store._state.item_instances[item_id] = ItemInstance(
            item_instance_id=item_id,
            life_id=life_id,
            item_code=item_code,
            definition_version=1,
            technique_id=None,
            issuance_id=UUID(int=base_id + 10_000 + offset),
            issuance_ordinal=0,
            quest_reward_grant_id=None,
            status=ItemInstanceStatus.OWNED,
            created_at=NOW,
            delivered_at=NOW,
            consumed_at=None,
            location=ItemLocation.INVENTORY,
        )
    return identities


@pytest.mark.asyncio
async def test_state_objectives_use_current_authoritative_targets() -> None:
    catalog = typed_catalog(
        ItemDeliveryObjectiveDefinition("deliver", "筑基丹", "foundation_pill", 3),
        TechniqueLayerObjectiveDefinition("technique", "冰冻术七层", "Gongfa_68726c", 7),
        RealmLevelObjectiveDefinition("realm", "筑基初期", 14),
    )
    quests, factory, account_id, life_id = await setup_services(catalog)
    target_instance = uuid4()
    other_instance = uuid4()
    grant_inventory_items(factory, life_id, "foundation_pill", 8, 18_100)
    factory.store._state.life_techniques[target_instance] = LifeTechnique(
        target_instance,
        life_id,
        "Gongfa_68726c",
        1,
        "qi",
        "练气",
        208,
        3_780,
        6,
        "active",
    )
    factory.store._state.life_techniques[other_instance] = LifeTechnique(
        other_instance,
        life_id,
        "GF_Other",
        1,
        "qi",
        "练气",
        3_780,
        3_780,
        13,
        "active",
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        14,
        0,
        208,
        None,
        1,
    )

    accepted = await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_002),
        expected_life_id=life_id,
    )
    objectives = response_body(accepted)["quest"]["objectives"]

    assert [(item["current"], item["required"], item["completed"]) for item in objectives] == [
        (8, 3, True),
        (6, 7, False),
        (14, 14, True),
    ]
    assert objectives[0]["objective_type"] == "item_delivery"
    assert objectives[0]["item_code"] == "foundation_pill"
    assert objectives[1]["item_code"] is None
    payload = response_body(accepted)["quest"]
    assert payload["description"] == QUEST_CATALOG.get_quest("first-steps").description
    assert payload["reward_previews"] == [
        {
            "reward_id": "starter-technique-manual",
            "kind": "fixed_item",
            "item_code": "technique_manual:GF_YinqiShu_01",
            "quantity": 1,
            "cultivation_amount": None,
        },
        {
            "reward_id": "starter-cultivation",
            "kind": "unrefined_cultivation",
            "item_code": None,
            "quantity": None,
            "cultivation_amount": 50,
        },
    ]

    factory.store._state.life_techniques[target_instance] = replace(
        factory.store._state.life_techniques[target_instance],
        current_layer=7,
    )
    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "ready_to_turn_in"

    factory.store._state.life_techniques[target_instance] = replace(
        factory.store._state.life_techniques[target_instance],
        status="abandoned",
    )
    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "active"
    assert state.providers[0].quests[0].objectives[1].current == 0


@pytest.mark.asyncio
async def test_inventory_objective_revision_advances_when_same_count_items_swap() -> None:
    catalog = typed_catalog(
        ItemDeliveryObjectiveDefinition("alpha", "玄铁", "item_alpha", 1),
        ItemDeliveryObjectiveDefinition("beta", "灵草", "item_beta", 1),
    )
    quests, factory, account_id, life_id = await setup_services(catalog)
    alpha_id = grant_inventory_items(factory, life_id, "item_alpha", 1, 18_500)[0]
    beta_id = grant_inventory_items(factory, life_id, "item_beta", 1, 18_510)[0]
    factory.store._state.item_instances[beta_id] = replace(
        factory.store._state.item_instances[beta_id],
        location=ItemLocation.STORAGE,
    )
    await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_050),
        expected_life_id=life_id,
    )
    before = await quests.get_interaction_state(account_id, ["objective-master"])

    async with factory() as uow:
        await uow.items.set_instance_location(
            item_instance_id=alpha_id,
            life_id=life_id,
            expected=ItemLocation.INVENTORY,
            destination=ItemLocation.STORAGE,
        )
        await uow.items.set_instance_location(
            item_instance_id=beta_id,
            life_id=life_id,
            expected=ItemLocation.STORAGE,
            destination=ItemLocation.INVENTORY,
        )
        await uow.commit()

    after = await quests.get_interaction_state(account_id, ["objective-master"])

    assert after.revision.objectives > before.revision.objectives
    assert [objective.current for objective in before.providers[0].quests[0].objectives] == [
        1,
        0,
    ]
    assert [objective.current for objective in after.providers[0].quests[0].objectives] == [
        0,
        1,
    ]


@pytest.mark.asyncio
async def test_nonlocking_inventory_projection_retries_changed_revision() -> None:
    life_id = UUID(int=18_520)
    old_item = ItemInstance(
        item_instance_id=UUID(int=18_521),
        life_id=life_id,
        item_code="item_alpha",
        definition_version=1,
        technique_id=None,
        issuance_id=UUID(int=18_522),
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.OWNED,
        created_at=NOW,
        delivered_at=NOW,
        consumed_at=None,
        location=ItemLocation.INVENTORY,
    )
    new_item = replace(old_item, item_instance_id=UUID(int=18_523))

    class ChangingInventory:
        def __init__(self) -> None:
            self.revisions = iter((0, 1, 1, 1))
            self.inventory_reads = 0

        async def get_inventory_revision(self, requested_life_id, *, for_update):
            assert requested_life_id == life_id
            assert for_update is False
            return next(self.revisions)

        async def get_inventory_instances(
            self,
            requested_life_id,
            item_codes=(),
            *,
            for_update,
        ):
            assert requested_life_id == life_id
            assert set(item_codes) == {"item_alpha"}
            assert for_update is False
            self.inventory_reads += 1
            return (old_item,) if self.inventory_reads == 1 else (new_item,)

    items = ChangingInventory()
    inventory, revision = await QuestService._load_inventory_objective_inputs(
        SimpleNamespace(items=items),
        life_id,
        {"item_alpha"},
        lock_items=False,
    )

    assert inventory == (new_item,)
    assert revision == 1
    assert items.inventory_reads == 2


@pytest.mark.asyncio
async def test_technique_objective_tracks_layer_gain_and_loss_from_investment() -> None:
    catalog = typed_catalog(
        TechniqueLayerObjectiveDefinition("technique", "冰冻术二层", "Gongfa_68726c", 2)
    )
    quests, factory, account_id, life_id = await setup_services(catalog)
    technique_instance = UUID(int=18_005)
    factory.store._state.life_techniques[technique_instance] = LifeTechnique(
        technique_instance,
        life_id,
        "Gongfa_68726c",
        1,
        "qi",
        "练气",
        0,
        3_780,
        0,
        "active",
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        1,
        0,
        0,
        None,
        1,
    )
    await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_006),
        expected_life_id=life_id,
    )

    async with factory() as uow:
        await uow.cultivation.apply_technique_investments(
            life_id=life_id,
            operation_id=UUID(int=18_007),
            session_id=None,
            changes=(
                TechniqueInvestmentChange(
                    technique_instance,
                    30,
                    "seclusion_realization",
                ),
            ),
            occurred_at=NOW,
        )
        await uow.commit()
    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "ready_to_turn_in"
    assert state.providers[0].quests[0].objectives[0].current == 2

    async with factory() as uow:
        await uow.cultivation.apply_technique_investments(
            life_id=life_id,
            operation_id=UUID(int=18_008),
            session_id=None,
            changes=(
                TechniqueInvestmentChange(
                    technique_instance,
                    -15,
                    "breakthrough_penalty",
                ),
            ),
            occurred_at=NOW + timedelta(seconds=1),
        )
        await uow.commit()
    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "active"
    assert state.providers[0].quests[0].objectives[0].current == 1


@pytest.mark.asyncio
async def test_kills_before_acceptance_do_not_advance_persisted_progress() -> None:
    objective = MythicMobKillObjectiveDefinition("hunt", "击杀苍狼", "AzureWolf", 2)
    catalog = typed_catalog(objective)
    quests, factory, account_id, life_id = await setup_services(catalog)
    progression = QuestEventProgressionService(catalog)

    await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_010),
        expected_life_id=life_id,
    )
    async with factory() as uow:
        changed = await progression.record_mythicmob_kill(
            uow,
            life_id=life_id,
            mob_internal_name="AzureWolf",
            occurred_at=NOW - timedelta(seconds=1),
        )
        await uow.commit()
    assert changed is False

    for offset in (1, 2):
        async with factory() as uow:
            changed = await progression.record_mythicmob_kill(
                uow,
                life_id=life_id,
                mob_internal_name="AzureWolf",
                occurred_at=NOW + timedelta(seconds=offset),
            )
            await uow.commit()
        assert changed is True

    state = await quests.get_interaction_state(account_id, ["objective-master"])
    projection = state.providers[0].quests[0]
    assert projection.state == "ready_to_turn_in"
    assert projection.objectives[0].current == 2
    assert factory.store._state.quest_revisions[life_id] == 3


@pytest.mark.asyncio
async def test_item_delivery_validates_all_stacks_before_atomic_consumption() -> None:
    catalog = typed_catalog(
        ItemDeliveryObjectiveDefinition("pills", "交付筑基丹", "foundation_pill", 2),
        ItemDeliveryObjectiveDefinition("tokens", "交付令牌", "trial_token", 1),
    )
    quests, factory, account_id, life_id = await setup_services(catalog)
    pill_ids = grant_inventory_items(factory, life_id, "foundation_pill", 2, 18_200)
    await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_020),
        expected_life_id=life_id,
    )

    rejected = await quests.turn_in(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_021),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    assert rejected.status_code == 409
    assert response_body(rejected)["error"]["code"] == "quest.not_ready"
    assert all(
        factory.store._state.item_instances[item_id].status is ItemInstanceStatus.OWNED
        for item_id in pill_ids
    )

    token_ids = grant_inventory_items(factory, life_id, "trial_token", 1, 18_210)
    operation_id = UUID(int=18_022)
    completed = await quests.turn_in(
        account_id,
        "typed-objectives",
        "objective-master",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=pill_ids + token_ids,
    )
    replayed = await quests.turn_in(
        account_id,
        "typed-objectives",
        "objective-master",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=pill_ids + token_ids,
    )

    assert completed == replayed
    payload = response_body(completed)
    assert payload["quest"]["state"] == "completed"
    assert all(item["completed"] for item in payload["quest"]["objectives"])
    assert all(
        factory.store._state.item_instances[item_id].status is ItemInstanceStatus.CONSUMED
        for item_id in pill_ids + token_ids
    )


@pytest.mark.asyncio
async def test_mixed_objectives_require_every_type() -> None:
    catalog = typed_catalog(
        ItemDeliveryObjectiveDefinition("deliver", "交付筑基丹", "foundation_pill", 1),
        MythicMobKillObjectiveDefinition("hunt", "击杀苍狼", "AzureWolf", 1),
        TechniqueLayerObjectiveDefinition("technique", "冰冻术二层", "Gongfa_68726c", 2),
        RealmLevelObjectiveDefinition("realm", "练气二层", 2),
    )
    quests, factory, account_id, life_id = await setup_services(catalog)
    technique_instance = uuid4()
    grant_inventory_items(factory, life_id, "foundation_pill", 1, 18_300)
    factory.store._state.life_techniques[technique_instance] = LifeTechnique(
        technique_instance,
        life_id,
        "Gongfa_68726c",
        1,
        "qi",
        "练气",
        30,
        3_780,
        2,
        "active",
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        2,
        0,
        30,
        None,
        1,
    )
    await quests.accept(
        account_id,
        "typed-objectives",
        "objective-master",
        UUID(int=18_030),
        expected_life_id=life_id,
    )

    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "active"
    assert [item.completed for item in state.providers[0].quests[0].objectives] == [
        True,
        False,
        True,
        True,
    ]

    async with factory() as uow:
        await QuestEventProgressionService(catalog).record_mythicmob_kill(
            uow,
            life_id=life_id,
            mob_internal_name="AzureWolf",
            occurred_at=NOW,
        )
        await uow.commit()
    state = await quests.get_interaction_state(account_id, ["objective-master"])
    assert state.providers[0].quests[0].state == "ready_to_turn_in"
