import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    ProximityBarkRule,
    QuestProviderDefinition,
    QuestStateCondition,
    RealmLevelCondition,
)
from immortal_mmo.quest.repository import QuestProgress, QuestProgressStatus
from immortal_mmo.quest.schemas import ProviderQuestState
from immortal_mmo.quest.service import QuestDefinitionVersionMismatchError, QuestService

NOW = datetime(2026, 7, 14, tzinfo=UTC)


async def logged_in_services() -> tuple[
    PlayerService, QuestService, FakeUnitOfWorkFactory, UUID, UUID
]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    players = PlayerService(factory)
    quests = QuestService(factory, clock=lambda: NOW)
    login = await players.login(UUID(int=10), "Quester")
    return players, quests, factory, login.account.account_id, login.current_life.life_id


def body(response) -> dict:
    return json.loads(response.body)


def projected_quest(quest_id: str, state: str) -> ProviderQuestState:
    action = {
        "ready_to_turn_in": "turn_in",
        "active": "remind",
        "available": "offer",
        "unavailable": "none",
        "completed": "talk",
    }[state]
    return ProviderQuestState(
        quest_id=quest_id,
        title=quest_id,
        description=f"{quest_id} description",
        category="main",
        state=state,
        action=action,
        dialogue_key=None,
        objectives=[],
        reward_previews=[],
    )


@pytest.mark.asyncio
async def test_accept_and_completed_turn_in_noops_do_not_increment_revision() -> None:
    players, quests, _, account_id, life_id = await logged_in_services()

    accepted = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=11),
        expected_life_id=life_id,
    )
    repeated_accept = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=12),
        expected_life_id=life_id,
    )
    await players.detect_current_life_spirit_root(account_id)
    completed = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=13),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    repeated_turn_in = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=14),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )

    assert body(accepted)["changed"] is True
    assert body(repeated_accept)["changed"] is False
    assert body(repeated_accept)["interaction_state"]["revision"]["quest"] == 1
    assert body(completed)["changed"] is True
    assert body(repeated_turn_in)["changed"] is False
    assert body(repeated_turn_in)["interaction_state"]["revision"]["quest"] == 2


@pytest.mark.asyncio
async def test_same_operation_id_replays_original_bytes_across_service_instances() -> None:
    _, quests, factory, account_id, life_id = await logged_in_services()
    operation_id = UUID(int=20)

    first = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
    )
    rebuilt = QuestService(factory, clock=lambda: NOW)
    replayed = await rebuilt.accept(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
    )

    assert replayed == first
    assert replayed.body is first.body or replayed.body == first.body


@pytest.mark.asyncio
async def test_domain_failure_is_frozen_and_replayed_without_raising() -> None:
    _, quests, factory, account_id, life_id = await logged_in_services()
    operation_id = UUID(int=21)

    first = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    replayed = await QuestService(factory).turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )

    assert first.status_code == 409
    assert body(first)["error"]["code"] == "quest.not_accepted"
    assert replayed == first


@pytest.mark.asyncio
async def test_definition_version_mismatch_is_a_frozen_domain_failure() -> None:
    _, quests, factory, account_id, life_id = await logged_in_services()
    async with factory() as uow:
        facts = await uow.players.get_current_life_facts(account_id, for_update=True)
        assert facts is not None
        uow._working_state.progresses[(facts.life_id, "first-steps")] = QuestProgress(
            life_id=facts.life_id,
            quest_id="first-steps",
            definition_version=999,
            status=QuestProgressStatus.ACTIVE,
            accepted_at=NOW,
            completed_at=None,
            revision=1,
        )
        uow._working_state.quest_revisions[facts.life_id] = 1
        await uow.commit()

    response = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=22),
        expected_life_id=life_id,
    )

    assert response.status_code == 409
    assert body(response)["error"]["code"] == "quest.definition_version_mismatch"


@pytest.mark.asyncio
async def test_quest_read_uses_repeatable_read_snapshot() -> None:
    _, quests, factory, account_id, _ = await logged_in_services()

    state = await quests.get_interaction_state(account_id, ["old-man"])

    assert state.providers[0].quests[0].state == "available"
    assert state.providers[0].proximity_bark is not None
    assert state.providers[0].proximity_bark.key == "old-man:first-steps-available"
    assert state.providers[0].proximity_bark.text == "最近太不太平了..."
    assert factory.isolations[-1] == "repeatable_read"


@pytest.mark.asyncio
async def test_proximity_bark_preserves_quest_state_speech_alongside_gui_projection() -> None:
    players, quests, _, account_id, life_id = await logged_in_services()

    available = await quests.get_interaction_state(account_id, ["old-man"])
    await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=31),
        expected_life_id=life_id,
    )
    active = await quests.get_interaction_state(account_id, ["old-man"])
    await players.detect_current_life_spirit_root(account_id)
    ready = await quests.get_interaction_state(account_id, ["old-man"])
    await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=32),
        expected_life_id=life_id,
        inventory_item_instance_ids=(),
    )
    completed = await quests.get_interaction_state(account_id, ["old-man"])

    assert available.providers[0].proximity_bark is not None
    assert available.providers[0].proximity_bark.key.endswith("first-steps-available")
    assert active.providers[0].proximity_bark is not None
    assert active.providers[0].proximity_bark.key.endswith("first-steps-active")
    assert ready.providers[0].proximity_bark is not None
    assert ready.providers[0].proximity_bark.key.endswith("first-steps-ready")
    assert completed.providers[0].proximity_bark is None


@pytest.mark.asyncio
async def test_realm_proximity_condition_loads_authoritative_level_and_revision() -> None:
    base_quest = QUEST_CATALOG.get_quest("first-steps")
    provider = replace(
        QUEST_CATALOG.get_provider("old-man"),
        proximity_bark_rules=(
            ProximityBarkRule(
                "cultivator",
                "你已经踏入修行。",
                conditions=(
                    QuestStateCondition("first-steps", ("available",)),
                    RealmLevelCondition(minimum_level=1),
                ),
                priority=10,
            ),
            ProximityBarkRule(
                "mortal",
                "先从凡人之身开始。",
                conditions=(
                    QuestStateCondition("first-steps", ("available",)),
                    RealmLevelCondition(maximum_level=0),
                ),
            ),
        ),
    )
    catalog = QuestDefinitionCatalog(quests=(base_quest,), providers=(provider,))
    _, _, factory, account_id, _ = await logged_in_services()
    quests = QuestService(factory, catalog, clock=lambda: NOW)

    mortal = await quests.get_interaction_state(account_id, ["old-man"])
    async with factory() as uow:
        facts = await uow.players.get_current_life_facts(account_id, for_update=True)
        assert facts is not None
        cultivation = await uow.cultivation.get_or_create_state(
            facts.life_id,
            for_update=True,
        )
        uow._working_state.cultivation_states[facts.life_id] = replace(
            cultivation,
            current_level=1,
            revision=cultivation.revision + 1,
        )
        await uow.commit()
    cultivator = await quests.get_interaction_state(account_id, ["old-man"])

    assert mortal.providers[0].proximity_bark is not None
    assert mortal.providers[0].proximity_bark.key == "old-man:mortal"
    assert cultivator.providers[0].proximity_bark is not None
    assert cultivator.providers[0].proximity_bark.key == "old-man:cultivator"
    assert cultivator.revision.objectives == mortal.revision.objectives + 1


@pytest.mark.asyncio
async def test_provider_without_proximity_rules_is_silent_but_still_projects_quests() -> None:
    silent_provider = replace(
        QUEST_CATALOG.get_provider("old-man"),
        proximity_bark_rules=(),
    )
    catalog = QuestDefinitionCatalog(
        quests=(QUEST_CATALOG.get_quest("first-steps"),),
        providers=(silent_provider,),
    )
    _, _, factory, account_id, _ = await logged_in_services()

    state = await QuestService(factory, catalog).get_interaction_state(
        account_id,
        ["old-man"],
    )

    assert state.providers[0].proximity_bark is None
    assert state.providers[0].quests[0].state == "available"


def test_provider_list_order_places_unavailable_before_completed() -> None:
    original = [
        projected_quest("completed", "completed"),
        projected_quest("available", "available"),
        projected_quest("unavailable", "unavailable"),
        projected_quest("active", "active"),
        projected_quest("ready", "ready_to_turn_in"),
    ]
    provider_order = {quest.quest_id: index for index, quest in enumerate(original)}

    ordered = sorted(
        original,
        key=lambda quest: QuestService._actionable_sort_key(quest, provider_order),
    )

    assert [quest.state for quest in ordered] == [
        "ready_to_turn_in",
        "active",
        "available",
        "unavailable",
        "completed",
    ]


@pytest.mark.asyncio
async def test_quest_read_rejects_loaded_progress_with_stale_definition_version() -> None:
    _, quests, factory, account_id, _ = await logged_in_services()
    async with factory() as uow:
        facts = await uow.players.get_current_life_facts(account_id, for_update=True)
        assert facts is not None
        uow._working_state.progresses[(facts.life_id, "first-steps")] = QuestProgress(
            life_id=facts.life_id,
            quest_id="first-steps",
            definition_version=999,
            status=QuestProgressStatus.ACTIVE,
            accepted_at=NOW,
            completed_at=None,
            revision=1,
        )
        await uow.commit()

    with pytest.raises(QuestDefinitionVersionMismatchError):
        await quests.get_interaction_state(account_id, ["old-man"])


@pytest.mark.asyncio
async def test_quest_read_rejects_stale_prerequisite_progress() -> None:
    prior = replace(QUEST_CATALOG.get_quest("first-steps"), quest_id="prior")
    follow_up = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        quest_id="follow-up",
        prerequisites=("prior",),
    )
    provider = QuestProviderDefinition(
        provider_id="old-man",
        display_name="老村民",
        main_quest_ids=("prior", "follow-up"),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(prior, follow_up), providers=(provider,))
    players, _, factory, account_id, _ = await logged_in_services()
    quests = QuestService(factory, catalog, clock=lambda: NOW)
    await players.detect_current_life_spirit_root(account_id)
    async with factory() as uow:
        facts = await uow.players.get_current_life_facts(account_id, for_update=True)
        assert facts is not None
        uow._working_state.progresses[(facts.life_id, "prior")] = QuestProgress(
            life_id=facts.life_id,
            quest_id="prior",
            definition_version=999,
            status=QuestProgressStatus.COMPLETED,
            accepted_at=NOW,
            completed_at=NOW,
            revision=1,
        )
        await uow.commit()

    with pytest.raises(QuestDefinitionVersionMismatchError):
        await quests.get_interaction_state(account_id, ["old-man"])


@pytest.mark.asyncio
async def test_accept_freezes_stale_prerequisite_definition_mismatch() -> None:
    prior = replace(QUEST_CATALOG.get_quest("first-steps"), quest_id="prior")
    follow_up = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        quest_id="follow-up",
        prerequisites=("prior",),
    )
    provider = QuestProviderDefinition(
        provider_id="old-man",
        display_name="老村民",
        main_quest_ids=("prior", "follow-up"),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(prior, follow_up), providers=(provider,))
    _, _, factory, account_id, life_id = await logged_in_services()
    quests = QuestService(factory, catalog, clock=lambda: NOW)
    async with factory() as uow:
        facts = await uow.players.get_current_life_facts(account_id, for_update=True)
        assert facts is not None
        uow._working_state.progresses[(facts.life_id, "prior")] = QuestProgress(
            life_id=facts.life_id,
            quest_id="prior",
            definition_version=999,
            status=QuestProgressStatus.COMPLETED,
            accepted_at=NOW,
            completed_at=NOW,
            revision=1,
        )
        await uow.commit()

    response = await quests.accept(
        account_id,
        "follow-up",
        "old-man",
        UUID(int=23),
        expected_life_id=life_id,
    )

    assert response.status_code == 409
    assert body(response)["error"]["code"] == "quest.definition_version_mismatch"
