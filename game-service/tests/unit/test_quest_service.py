import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import QuestProviderDefinition
from immortal_mmo.quest.repository import QuestProgress, QuestProgressStatus
from immortal_mmo.quest.service import QuestDefinitionVersionMismatchError, QuestService

NOW = datetime(2026, 7, 14, tzinfo=UTC)


async def logged_in_services() -> tuple[PlayerService, QuestService, FakeUnitOfWorkFactory, UUID]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    players = PlayerService(factory)
    quests = QuestService(factory, clock=lambda: NOW)
    login = await players.login(UUID(int=10), "Quester")
    return players, quests, factory, login.account.account_id


def body(response) -> dict:
    return json.loads(response.body)


@pytest.mark.asyncio
async def test_accept_and_completed_turn_in_noops_do_not_increment_revision() -> None:
    players, quests, _, account_id = await logged_in_services()

    accepted = await quests.accept(account_id, "first-steps", "old-man", UUID(int=11))
    repeated_accept = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=12),
    )
    await players.detect_current_life_spirit_root(account_id)
    completed = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=13),
        inventory_item_instance_ids=(),
    )
    repeated_turn_in = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        UUID(int=14),
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
    _, quests, factory, account_id = await logged_in_services()
    operation_id = UUID(int=20)

    first = await quests.accept(account_id, "first-steps", "old-man", operation_id)
    rebuilt = QuestService(factory, clock=lambda: NOW)
    replayed = await rebuilt.accept(account_id, "first-steps", "old-man", operation_id)

    assert replayed == first
    assert replayed.body is first.body or replayed.body == first.body


@pytest.mark.asyncio
async def test_domain_failure_is_frozen_and_replayed_without_raising() -> None:
    _, quests, factory, account_id = await logged_in_services()
    operation_id = UUID(int=21)

    first = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        inventory_item_instance_ids=(),
    )
    replayed = await QuestService(factory).turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
        inventory_item_instance_ids=(),
    )

    assert first.status_code == 409
    assert body(first)["error"]["code"] == "quest.not_accepted"
    assert replayed == first


@pytest.mark.asyncio
async def test_definition_version_mismatch_is_a_frozen_domain_failure() -> None:
    _, quests, factory, account_id = await logged_in_services()
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

    response = await quests.accept(account_id, "first-steps", "old-man", UUID(int=22))

    assert response.status_code == 409
    assert body(response)["error"]["code"] == "quest.definition_version_mismatch"


@pytest.mark.asyncio
async def test_quest_read_uses_repeatable_read_snapshot() -> None:
    _, quests, factory, account_id = await logged_in_services()

    state = await quests.get_interaction_state(account_id, ["old-man"])

    assert state.providers[0].quests[0].state == "available"
    assert factory.isolations[-1] == "repeatable_read"


@pytest.mark.asyncio
async def test_quest_read_rejects_loaded_progress_with_stale_definition_version() -> None:
    _, quests, factory, account_id = await logged_in_services()
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
    players, _, factory, account_id = await logged_in_services()
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
    _, _, factory, account_id = await logged_in_services()
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
    )

    assert response.status_code == 409
    assert body(response)["error"]["code"] == "quest.definition_version_mismatch"
