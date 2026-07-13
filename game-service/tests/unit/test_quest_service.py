from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier
from threading import Event as ThreadEvent
from uuid import UUID

import pytest

from immortal_mmo.player.schemas import CurrentLifeQuestFacts, SpiritRoot
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestObjectiveDefinition,
    QuestObjectiveType,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
)
from immortal_mmo.quest.repository import InMemoryQuestRepository
from immortal_mmo.quest.service import (
    QuestIdempotencyConflictError,
    QuestNotAcceptedError,
    QuestNotAvailableError,
    QuestNotFoundError,
    QuestNotReadyError,
    QuestProviderMismatchError,
    QuestProviderNotFoundError,
    QuestService,
)

ACCOUNT_ID = UUID(int=1)
LIFE_ID = UUID(int=10)
NOW = datetime(2026, 7, 13, tzinfo=UTC)


def spirit_root() -> SpiritRoot:
    return SpiritRoot(
        quality="variant",
        label="异灵根",
        elements=["金"],
        mutated_element="金雷",
        variant_element="雷",
    )


class FactsReader:
    def __init__(self, facts: CurrentLifeQuestFacts) -> None:
        self.facts = facts
        self.calls = 0

    def get_current_life_facts(self, account_id: UUID) -> CurrentLifeQuestFacts:
        assert account_id == self.facts.account_id
        self.calls += 1
        return self.facts


class CountingRepository(InMemoryQuestRepository):
    def __init__(self) -> None:
        super().__init__()
        self.bulk_calls = 0

    def get_progress_snapshot(self, life_id, quest_ids):
        self.bulk_calls += 1
        return super().get_progress_snapshot(life_id, quest_ids)


class ConcurrentSnapshotRepository(CountingRepository):
    def __init__(self) -> None:
        super().__init__()
        self._snapshot_barrier = Barrier(2)

    def get_progress_snapshot(self, life_id, quest_ids):
        snapshot = super().get_progress_snapshot(life_id, quest_ids)
        self._snapshot_barrier.wait(timeout=2)
        return snapshot


class LockProbeQuestService(QuestService):
    def __init__(self, reader, repository, catalog) -> None:
        super().__init__(reader, repository, catalog, clock=lambda: NOW)
        self._probe_repository = repository

    def _build_mutation_result(self, facts, operation):
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            probe = executor.submit(
                self._probe_repository.get_quest_revision,
                facts.life_id,
            )
            assert probe.result(timeout=0.2) == operation.snapshot.quest_revision
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return super()._build_mutation_result(facts, operation)


class SlowProjectionQuestService(QuestService):
    def __init__(self, reader, repository, entered: ThreadEvent, release: ThreadEvent) -> None:
        super().__init__(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
        self._entered = entered
        self._release = release

    def _build_mutation_result(self, facts, operation):
        self._entered.set()
        assert self._release.wait(timeout=2)
        return super()._build_mutation_result(facts, operation)


class FailingProjectionQuestService(QuestService):
    def _build_mutation_result(self, facts, operation):
        raise ValueError("projection failed")


def facts(*, life_id: UUID = LIFE_ID, root: SpiritRoot | None = None, revision: int = 1):
    return CurrentLifeQuestFacts(
        account_id=ACCOUNT_ID,
        life_id=life_id,
        generation_no=1,
        spirit_root=root,
        revision=revision,
    )


def service(
    *,
    player_facts: CurrentLifeQuestFacts | None = None,
    catalog: QuestDefinitionCatalog = QUEST_CATALOG,
):
    reader = FactsReader(player_facts or facts())
    repository = CountingRepository()
    return QuestService(reader, repository, catalog, clock=lambda: NOW), reader, repository


def test_aggregate_derives_available_state_with_one_facts_and_bulk_read() -> None:
    quest_service, reader, repository = service()

    state = quest_service.get_interaction_state(ACCOUNT_ID, ["old-man"])

    provider = state.providers[0]
    assert provider.provider_id == "old-man"
    assert provider.quests[0].state == "available"
    assert provider.quests[0].action == "offer"
    assert provider.direct_action_quest_id == "first-steps"
    assert provider.actionable_quest_ids == ["first-steps"]
    assert provider.proximity_bark.model_dump() == {
        "key": "first-steps:available",
        "text": "最近太不太平了...",
        "cooldown_seconds": 60,
    }
    assert state.tracked_quest is None
    assert reader.calls == 1
    assert repository.bulk_calls == 1


def test_accept_moves_to_active_and_returns_complete_projection() -> None:
    quest_service, _, _ = service()

    mutation = quest_service.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        UUID(int=100),
    )

    assert mutation.changed is True
    assert mutation.quest.state == "active"
    assert mutation.interaction_state.providers[0].quests[0].state == "active"
    assert mutation.interaction_state.tracked_quest.model_dump() == {
        "quest_id": "first-steps",
        "title": "初入凡尘",
        "state": "active",
        "objectives": [
            {
                "objective_id": "detect-spirit-root",
                "title": "灵根检测",
                "current": 0,
                "required": 1,
                "completed": False,
            }
        ],
        "next_action_hint": "前往鉴灵师处",
    }


def test_ready_is_derived_from_current_life_spirit_root() -> None:
    quest_service, reader, _ = service()
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", UUID(int=101))

    reader.facts = facts(root=spirit_root(), revision=2)
    state = quest_service.get_interaction_state(ACCOUNT_ID, ["old-man"])

    assert state.providers[0].quests[0].state == "ready_to_turn_in"
    assert state.providers[0].quests[0].action == "turn_in"
    assert state.tracked_quest.objectives[0].current == 1
    assert state.tracked_quest.objectives[0].completed is True
    assert state.tracked_quest.next_action_hint == "返回老村民处"


def test_accept_after_prior_detection_is_immediately_ready_and_turns_in_once() -> None:
    quest_service, _, _ = service(player_facts=facts(root=spirit_root(), revision=2))
    accepted = quest_service.accept(
        ACCOUNT_ID, "first-steps", "old-man", UUID(int=102)
    )

    completed = quest_service.turn_in(
        ACCOUNT_ID, "first-steps", "old-man", UUID(int=103)
    )
    repeated = quest_service.turn_in(
        ACCOUNT_ID, "first-steps", "old-man", UUID(int=104)
    )

    assert accepted.quest.state == "ready_to_turn_in"
    assert completed.changed is True
    assert completed.quest.state == "completed"
    assert completed.interaction_state.tracked_quest is None
    assert repeated.changed is False
    assert repeated.quest.state == "completed"


def test_progress_is_isolated_by_current_life() -> None:
    quest_service, reader, _ = service(player_facts=facts(root=spirit_root()))
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", UUID(int=105))
    quest_service.turn_in(ACCOUNT_ID, "first-steps", "old-man", UUID(int=106))

    reader.facts = facts(life_id=UUID(int=11), root=None, revision=1)
    new_life = quest_service.get_interaction_state(ACCOUNT_ID, ["old-man"])

    assert new_life.providers[0].quests[0].state == "available"
    assert new_life.revision.quest == 0


def test_provider_and_quest_errors_are_stable() -> None:
    quest_service, _, _ = service()

    with pytest.raises(QuestProviderNotFoundError):
        quest_service.get_interaction_state(ACCOUNT_ID, ["missing"])
    with pytest.raises(QuestNotFoundError):
        quest_service.accept(ACCOUNT_ID, "missing", "old-man", UUID(int=107))
    with pytest.raises(QuestProviderNotFoundError):
        quest_service.accept(ACCOUNT_ID, "first-steps", "missing", UUID(int=108))

    first_steps = QUEST_CATALOG.get_quest("first-steps")
    catalog = QuestDefinitionCatalog(
        quests=(first_steps,),
        providers=(
            QUEST_CATALOG.get_provider("old-man"),
            QuestProviderDefinition(
                provider_id="other",
                display_name="Other",
                main_quest_ids=(),
                side_quest_ids=(),
            ),
        ),
    )
    mismatch_service, _, _ = service(catalog=catalog)
    with pytest.raises(QuestProviderMismatchError):
        mismatch_service.accept(ACCOUNT_ID, "first-steps", "other", UUID(int=109))


def test_unknown_target_and_provider_mismatch_failures_are_repository_replayable() -> None:
    first_steps = QUEST_CATALOG.get_quest("first-steps")
    catalog = QuestDefinitionCatalog(
        quests=(first_steps,),
        providers=(
            QUEST_CATALOG.get_provider("old-man"),
            QuestProviderDefinition(
                provider_id="other",
                display_name="Other",
                main_quest_ids=(),
                side_quest_ids=(),
            ),
        ),
    )
    reader = FactsReader(facts())
    repository = CountingRepository()
    first_service = QuestService(reader, repository, catalog, clock=lambda: NOW)
    cases = (
        ("missing", "old-man", QuestNotFoundError, UUID(int=138)),
        ("first-steps", "missing", QuestProviderNotFoundError, UUID(int=139)),
        ("first-steps", "other", QuestProviderMismatchError, UUID(int=140)),
    )

    for quest_id, provider_id, error_type, operation_id in cases:
        with pytest.raises(error_type) as first:
            first_service.accept(ACCOUNT_ID, quest_id, provider_id, operation_id)
        rebuilt = QuestService(reader, repository, catalog, clock=lambda: NOW)
        with pytest.raises(error_type) as replay:
            rebuilt.accept(ACCOUNT_ID, quest_id, provider_id, operation_id)
        assert replay.value.code == first.value.code
        with pytest.raises(QuestIdempotencyConflictError):
            rebuilt.turn_in(ACCOUNT_ID, quest_id, provider_id, operation_id)


def test_premature_turn_in_is_rejected_without_mutation() -> None:
    quest_service, _, repository = service()

    with pytest.raises(QuestNotAcceptedError):
        quest_service.turn_in(ACCOUNT_ID, "first-steps", "old-man", UUID(int=110))
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", UUID(int=111))
    with pytest.raises(QuestNotReadyError):
        quest_service.turn_in(ACCOUNT_ID, "first-steps", "old-man", UUID(int=112))

    assert repository.get_quest_revision(LIFE_ID) == 1


def test_operation_conflict_becomes_stable_domain_error() -> None:
    quest_service, _, _ = service(player_facts=facts(root=spirit_root()))
    operation_id = UUID(int=113)
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", operation_id)

    with pytest.raises(QuestIdempotencyConflictError):
        quest_service.turn_in(ACCOUNT_ID, "first-steps", "old-man", operation_id)


def test_operation_conflict_precedes_target_and_rule_validation() -> None:
    quest_service, _, _ = service()
    operation_id = UUID(int=118)
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", operation_id)

    with pytest.raises(QuestIdempotencyConflictError):
        quest_service.turn_in(ACCOUNT_ID, "missing", "missing", operation_id)


def test_same_operation_replays_frozen_full_response_after_state_advances() -> None:
    quest_service, reader, _ = service()
    operation_id = UUID(int=119)
    accepted = quest_service.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        operation_id,
    )
    frozen_body = accepted.model_dump(mode="json")
    reader.facts = facts(root=spirit_root(), revision=2)
    quest_service.turn_in(ACCOUNT_ID, "first-steps", "old-man", UUID(int=120))

    replayed = quest_service.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        operation_id,
    )

    assert replayed.model_dump(mode="json") == frozen_body
    assert replayed.quest.state == "active"
    assert replayed.interaction_state.revision.quest == 1


def test_rebuilt_service_replays_repository_owned_frozen_response() -> None:
    reader = FactsReader(facts())
    repository = CountingRepository()
    service_a = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
    operation_id = UUID(int=125)
    accepted = service_a.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        operation_id,
    )
    frozen_body = accepted.model_dump(mode="json")
    reader.facts = facts(root=spirit_root(), revision=2)
    service_a.turn_in(ACCOUNT_ID, "first-steps", "old-man", UUID(int=126))

    service_b = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
    replayed = service_b.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        operation_id,
    )

    assert replayed.model_dump(mode="json") == frozen_body


def test_rebuilt_service_checks_repository_conflict_before_rules() -> None:
    reader = FactsReader(facts())
    repository = CountingRepository()
    service_a = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
    operation_id = UUID(int=127)
    service_a.accept(ACCOUNT_ID, "first-steps", "old-man", operation_id)
    service_b = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)

    with pytest.raises(QuestIdempotencyConflictError):
        service_b.turn_in(ACCOUNT_ID, "missing", "missing", operation_id)


def test_projection_and_serialization_run_after_repository_lock_is_released() -> None:
    reader = FactsReader(facts())
    repository = CountingRepository()
    quest_service = LockProbeQuestService(reader, repository, QUEST_CATALOG)

    result = quest_service.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        UUID(int=128),
    )

    assert result.changed is True


def test_same_key_across_services_waits_for_repository_finalization() -> None:
    reader = FactsReader(facts())
    repository = CountingRepository()
    entered = ThreadEvent()
    release = ThreadEvent()
    service_a = SlowProjectionQuestService(reader, repository, entered, release)
    service_b = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
    operation_id = UUID(int=129)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            service_a.accept,
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )
        assert entered.wait(timeout=1)
        second = executor.submit(
            service_b.accept,
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )
        assert second.done() is False
        release.set()
        first_result = first.result(timeout=2)
        second_result = second.result(timeout=2)

    assert second_result.model_dump(mode="json") == first_result.model_dump(mode="json")


def test_projection_failure_preserves_pending_mutation_for_retry_takeover() -> None:
    reader = FactsReader(facts())
    repository = CountingRepository()
    failing = FailingProjectionQuestService(
        reader,
        repository,
        QUEST_CATALOG,
        clock=lambda: NOW,
    )
    operation_id = UUID(int=130)

    with pytest.raises(ValueError, match="projection failed"):
        failing.accept(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )

    assert repository.get_quest_revision(LIFE_ID) == 1
    assert repository.get_progresses(LIFE_ID, {"first-steps"})["first-steps"].status.value == (
        "active"
    )

    retry = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)
    result = retry.accept(
        ACCOUNT_ID,
        "first-steps",
        "old-man",
        operation_id,
    )

    assert result.changed is True
    assert result.interaction_state.revision.quest == 1


def test_unavailable_quest_cannot_be_accepted() -> None:
    locked = definition(
        "locked",
        QuestCategory.MAIN,
        prerequisites=("prerequisite",),
    )
    prerequisite = definition("prerequisite", QuestCategory.MAIN)
    catalog = QuestDefinitionCatalog(
        quests=(locked, prerequisite),
        providers=(
            QuestProviderDefinition(
                provider_id="multi",
                display_name="Multi",
                main_quest_ids=("locked", "prerequisite"),
                side_quest_ids=(),
            ),
        ),
    )
    quest_service, _, _ = service(catalog=catalog)

    with pytest.raises(QuestNotAvailableError):
        quest_service.accept(ACCOUNT_ID, "locked", "multi", UUID(int=121))


def test_not_accepted_failure_is_frozen_before_later_state_changes() -> None:
    quest_service, reader, repository = service()
    operation_id = UUID(int=131)
    with pytest.raises(QuestNotAcceptedError) as first:
        quest_service.turn_in(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", UUID(int=132))
    reader.facts = facts(root=spirit_root(), revision=2)
    rebuilt = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)

    with pytest.raises(QuestNotAcceptedError) as replay:
        rebuilt.turn_in(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )
    with pytest.raises(QuestIdempotencyConflictError):
        rebuilt.accept(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )

    assert replay.value.code == first.value.code
    assert replay.value.message == first.value.message


def test_not_ready_failure_is_frozen_after_objective_becomes_complete() -> None:
    quest_service, reader, repository = service()
    quest_service.accept(ACCOUNT_ID, "first-steps", "old-man", UUID(int=133))
    operation_id = UUID(int=134)
    with pytest.raises(QuestNotReadyError):
        quest_service.turn_in(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )
    reader.facts = facts(root=spirit_root(), revision=2)
    rebuilt = QuestService(reader, repository, QUEST_CATALOG, clock=lambda: NOW)

    with pytest.raises(QuestNotReadyError):
        rebuilt.turn_in(
            ACCOUNT_ID,
            "first-steps",
            "old-man",
            operation_id,
        )


def test_not_available_failure_is_frozen_after_prerequisite_unlocks() -> None:
    locked = definition(
        "locked",
        QuestCategory.MAIN,
        prerequisites=("prerequisite",),
    )
    prerequisite = definition(
        "prerequisite",
        QuestCategory.MAIN,
        ready_without_root=True,
    )
    catalog = QuestDefinitionCatalog(
        quests=(locked, prerequisite),
        providers=(
            QuestProviderDefinition(
                provider_id="multi",
                display_name="Multi",
                main_quest_ids=("locked", "prerequisite"),
                side_quest_ids=(),
            ),
        ),
    )
    quest_service, reader, repository = service(catalog=catalog)
    operation_id = UUID(int=135)
    with pytest.raises(QuestNotAvailableError):
        quest_service.accept(ACCOUNT_ID, "locked", "multi", operation_id)
    quest_service.accept(ACCOUNT_ID, "prerequisite", "multi", UUID(int=136))
    quest_service.turn_in(ACCOUNT_ID, "prerequisite", "multi", UUID(int=137))
    rebuilt = QuestService(reader, repository, catalog, clock=lambda: NOW)

    with pytest.raises(QuestNotAvailableError):
        rebuilt.accept(ACCOUNT_ID, "locked", "multi", operation_id)


def definition(
    quest_id: str,
    category: QuestCategory,
    *,
    prerequisites: tuple[str, ...] = (),
    ready_without_root: bool = False,
) -> QuestDefinition:
    objectives = () if ready_without_root else (
        QuestObjectiveDefinition(
            objective_id="root",
            objective_type=QuestObjectiveType.CURRENT_LIFE_SPIRIT_ROOT_PRESENT,
            label="灵根检测",
            required=1,
        ),
    )
    return QuestDefinition(
        quest_id=quest_id,
        version=1,
        title=quest_id,
        category=category,
        repeatability=QuestRepeatability.ONCE_PER_LIFE,
        prerequisites=prerequisites,
        objectives=objectives,
        provider_ids=("multi",),
        turn_in_provider_ids=("multi",),
        dialogue_keys=QuestDialogueKeys(
            available=f"{quest_id}.available",
            active=f"{quest_id}.active",
            ready_to_turn_in=f"{quest_id}.ready",
            completed=f"{quest_id}.completed",
        ),
        presentation=QuestPresentationHints(
            active_next_action="active",
            ready_next_action="ready",
            available_proximity_text="available",
            active_proximity_text="active",
            ready_proximity_text="ready",
        ),
    )


def test_actionable_order_and_multi_quest_direct_action_contract() -> None:
    quests = (
        definition("available-main", QuestCategory.MAIN),
        definition("active-main", QuestCategory.MAIN),
        definition("ready-side", QuestCategory.SIDE, ready_without_root=True),
        definition("available-side", QuestCategory.SIDE),
    )
    catalog = QuestDefinitionCatalog(
        quests=quests,
        providers=(
            QuestProviderDefinition(
                provider_id="multi",
                display_name="Multi",
                main_quest_ids=("available-main", "active-main"),
                side_quest_ids=("ready-side", "available-side"),
            ),
        ),
    )
    quest_service, _, repository = service(catalog=catalog)
    repository.accept(
        life_id=LIFE_ID,
        quest_id="active-main",
        provider_id="multi",
        definition_version=1,
        operation_id=UUID(int=114),
        accepted_at=NOW,
    )
    repository.accept(
        life_id=LIFE_ID,
        quest_id="ready-side",
        provider_id="multi",
        definition_version=1,
        operation_id=UUID(int=115),
        accepted_at=NOW,
    )

    projection = quest_service.get_interaction_state(ACCOUNT_ID, ["multi"]).providers[0]

    assert projection.actionable_quest_ids == [
        "ready-side",
        "active-main",
        "available-main",
        "available-side",
    ]
    assert projection.direct_action_quest_id is None


def test_concurrent_different_quest_response_revision_has_matching_fresh_projection() -> None:
    quests = (
        definition("quest-a", QuestCategory.MAIN),
        definition("quest-b", QuestCategory.MAIN),
    )
    catalog = QuestDefinitionCatalog(
        quests=quests,
        providers=(
            QuestProviderDefinition(
                provider_id="multi",
                display_name="Multi",
                main_quest_ids=("quest-a", "quest-b"),
                side_quest_ids=(),
            ),
        ),
    )
    reader = FactsReader(facts())
    repository = ConcurrentSnapshotRepository()
    quest_service = QuestService(reader, repository, catalog, clock=lambda: NOW)

    def accept(quest_id: str, operation_int: int):
        return quest_service.accept(
            ACCOUNT_ID,
            quest_id,
            "multi",
            UUID(int=operation_int),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(accept, "quest-a", 122),
            executor.submit(accept, "quest-b", 123),
        )
        results = [future.result(timeout=3) for future in futures]

    newest = max(results, key=lambda result: result.interaction_state.revision.quest)
    assert newest.interaction_state.revision.quest == 2
    assert {
        quest.quest_id: quest.state
        for quest in newest.interaction_state.providers[0].quests
    } == {"quest-a": "active", "quest-b": "active"}


def test_provider_projection_respects_separate_giver_and_turn_in_permissions() -> None:
    base = definition("split", QuestCategory.MAIN)
    split = replace(
        base,
        provider_ids=("giver",),
        turn_in_provider_ids=("turner",),
    )
    catalog = QuestDefinitionCatalog(
        quests=(split,),
        providers=(
            QuestProviderDefinition(
                provider_id="giver",
                display_name="Giver",
                main_quest_ids=("split",),
                side_quest_ids=(),
            ),
            QuestProviderDefinition(
                provider_id="turner",
                display_name="Turner",
                main_quest_ids=("split",),
                side_quest_ids=(),
            ),
        ),
    )
    quest_service, reader, _ = service(catalog=catalog)

    available = quest_service.get_interaction_state(
        ACCOUNT_ID,
        ["giver", "turner"],
    )
    assert available.providers[0].quests[0].action == "offer"
    assert available.providers[0].direct_action_quest_id == "split"
    assert available.providers[1].quests[0].action == "none"
    assert available.providers[1].direct_action_quest_id is None

    quest_service.accept(ACCOUNT_ID, "split", "giver", UUID(int=124))
    reader.facts = facts(root=spirit_root(), revision=2)
    ready = quest_service.get_interaction_state(
        ACCOUNT_ID,
        ["giver", "turner"],
    )

    assert ready.providers[0].quests[0].state == "ready_to_turn_in"
    assert ready.providers[0].quests[0].action == "remind"
    assert ready.providers[1].quests[0].action == "turn_in"


def test_completed_quest_unlocks_prerequisite_without_extra_unlock_state() -> None:
    first = definition("first", QuestCategory.MAIN, ready_without_root=True)
    future = definition("future", QuestCategory.MAIN, prerequisites=("first",))
    catalog = QuestDefinitionCatalog(
        quests=(first, future),
        providers=(
            QuestProviderDefinition(
                provider_id="multi",
                display_name="Multi",
                main_quest_ids=("first", "future"),
                side_quest_ids=(),
            ),
        ),
    )
    quest_service, _, _ = service(catalog=catalog)
    quest_service.accept(ACCOUNT_ID, "first", "multi", UUID(int=116))
    quest_service.turn_in(ACCOUNT_ID, "first", "multi", UUID(int=117))

    state = quest_service.get_interaction_state(ACCOUNT_ID, ["multi"])

    assert [quest.state for quest in state.providers[0].quests] == ["available", "completed"]
    assert state.providers[0].direct_action_quest_id == "future"
