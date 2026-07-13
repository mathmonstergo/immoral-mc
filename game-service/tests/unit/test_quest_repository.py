from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from immortal_mmo.quest.repository import (
    FrozenQuestDomainError,
    InMemoryQuestRepository,
    OperationIdConflictError,
    QuestFinalizedFailure,
    QuestFinalizedOperation,
    QuestOperationCommand,
    QuestOperationOwner,
    QuestOperationProjectionContext,
    QuestOperationWaiter,
    QuestProgressStatus,
)

LIFE_ID = UUID(int=101)
FIRST_OPERATION = UUID(int=201)
NOW = datetime(2026, 7, 13, tzinfo=UTC)


class MutableMonotonic:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def projection_context() -> QuestOperationProjectionContext:
    return QuestOperationProjectionContext(
        account_id=UUID(int=1),
        life_id=LIFE_ID,
        revision=1,
        spirit_root_present=False,
    )


def finalize(repository, attempt, payload: str = "{}") -> QuestFinalizedOperation:
    if isinstance(attempt, QuestFinalizedOperation):
        return attempt
    assert isinstance(attempt, QuestOperationOwner)
    return repository.finalize_operation(attempt, payload)


def commit_accept(repository, **kwargs) -> QuestFinalizedOperation:
    return finalize(repository, repository.accept(**kwargs))


def commit_complete(repository, **kwargs) -> QuestFinalizedOperation:
    return finalize(repository, repository.complete(**kwargs))


def test_accept_creates_one_life_scoped_progress_and_advances_revision() -> None:
    repository = InMemoryQuestRepository()

    result = commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )

    assert result.changed is True
    assert result.progress.life_id == LIFE_ID
    assert result.progress.quest_id == "first-steps"
    assert result.progress.status is QuestProgressStatus.ACTIVE
    assert result.progress.accepted_at == NOW
    assert result.progress.completed_at is None
    assert result.progress.revision == 1
    assert result.quest_revision == 1
    assert repository.get_quest_revision(LIFE_ID) == 1


def test_accept_is_copy_on_write_and_semantically_idempotent() -> None:
    repository = InMemoryQuestRepository()
    first = commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )

    repeated = commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=UUID(int=202),
        accepted_at=NOW + timedelta(seconds=1),
    )

    assert repeated.changed is False
    assert repeated.progress is first.progress
    assert repeated.quest_revision == 1


def test_bulk_progress_reads_are_life_scoped() -> None:
    repository = InMemoryQuestRepository()
    commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )
    other_life = UUID(int=102)
    commit_accept(repository,
        life_id=other_life,
        quest_id="other",
        provider_id="other-provider",
        definition_version=1,
        operation_id=UUID(int=203),
        accepted_at=NOW,
    )

    assert repository.get_progresses(LIFE_ID, {"first-steps", "missing"}) == {
        "first-steps": repository.get_progresses(LIFE_ID, {"first-steps"})["first-steps"]
    }
    assert repository.get_progresses(LIFE_ID, {"other"}) == {}


def test_complete_transitions_once_and_replay_returns_stored_result() -> None:
    repository = InMemoryQuestRepository()
    commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )
    operation_id = UUID(int=204)

    completed = commit_complete(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        operation_id=operation_id,
        completed_at=NOW + timedelta(minutes=1),
    )
    replayed = commit_complete(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        operation_id=operation_id,
        completed_at=NOW + timedelta(minutes=2),
    )
    repeated = commit_complete(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        operation_id=UUID(int=205),
        completed_at=NOW + timedelta(minutes=3),
    )

    assert completed.changed is True
    assert completed.progress.status is QuestProgressStatus.COMPLETED
    assert completed.progress.completed_at == NOW + timedelta(minutes=1)
    assert completed.progress.revision == 2
    assert replayed is completed
    assert repeated.changed is False
    assert repeated.progress is completed.progress
    assert repository.get_quest_revision(LIFE_ID) == 2


def test_operation_ledger_replays_frozen_response_payload() -> None:
    repository = InMemoryQuestRepository()
    operation_id = UUID(int=206)
    owner = repository.accept(
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=operation_id,
        accepted_at=NOW,
    )
    assert isinstance(owner, QuestOperationOwner)
    accepted = repository.finalize_operation(
        owner,
        f'{{"changed":true,"revision":{owner.state.snapshot.quest_revision}}}',
    )
    commit_complete(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        operation_id=UUID(int=207),
        completed_at=NOW,
    )

    replayed = repository.accept(
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=operation_id,
        accepted_at=NOW,
    )

    assert replayed is accepted
    assert replayed.frozen_response_json == '{"changed":true,"revision":1}'


def test_owner_release_preserves_mutation_for_retry_takeover() -> None:
    repository = InMemoryQuestRepository()
    operation_id = UUID(int=208)
    first_owner = repository.accept(
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=operation_id,
        accepted_at=NOW,
    )
    assert isinstance(first_owner, QuestOperationOwner)
    repository.release_operation_owner(first_owner)

    takeover = repository.accept(
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=operation_id,
        accepted_at=NOW + timedelta(seconds=1),
    )

    assert isinstance(takeover, QuestOperationOwner)
    assert takeover.state.changed is True
    assert takeover.state.snapshot.quest_revision == 1
    assert takeover.state.progress is first_owner.state.progress
    assert repository.get_quest_revision(LIFE_ID) == 1
    assert repository.get_operation_result(LIFE_ID, operation_id) is None

    with pytest.raises(ValueError, match="requires a frozen response"):
        repository.finalize_operation(takeover, "")
    assert repository.get_operation_result(LIFE_ID, operation_id) is None

    finalized = repository.finalize_operation(takeover, "{}")
    assert finalized.frozen_response_json == "{}"


def test_stale_owner_lease_can_be_taken_over_and_old_token_cannot_finalize() -> None:
    monotonic = MutableMonotonic()
    repository = InMemoryQuestRepository(
        monotonic=monotonic,
        operation_lease_seconds=2.0,
    )
    owner = repository.reserve_operation(
        life_id=LIFE_ID,
        operation_id=UUID(int=209),
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        projection_context=projection_context(),
    )
    assert isinstance(owner, QuestOperationOwner)
    waiter = repository.reserve_operation(
        life_id=LIFE_ID,
        operation_id=UUID(int=209),
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        projection_context=projection_context(),
    )
    assert isinstance(waiter, QuestOperationWaiter)
    assert 0 < waiter.wait_timeout_seconds <= 2.0

    monotonic.advance(2.1)
    takeover = repository.reserve_operation(
        life_id=LIFE_ID,
        operation_id=UUID(int=209),
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        projection_context=projection_context(),
    )
    assert isinstance(takeover, QuestOperationOwner)
    assert takeover.owner_token != owner.owner_token

    failure = FrozenQuestDomainError(
        status_code=404,
        code="quest.not_found",
        message="Quest was not found.",
        retryable=False,
    )
    with pytest.raises(RuntimeError, match="ownership was lost"):
        repository.finalize_failure(owner, failure)
    finalized = repository.finalize_failure(takeover, failure)
    assert isinstance(finalized, QuestFinalizedFailure)


def test_wait_for_pending_operation_has_bounded_timeout() -> None:
    monotonic = MutableMonotonic()
    repository = InMemoryQuestRepository(
        monotonic=monotonic,
        operation_lease_seconds=1.5,
        operation_wait_seconds=0.01,
    )
    operation_id = UUID(int=210)
    repository.reserve_operation(
        life_id=LIFE_ID,
        operation_id=operation_id,
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        projection_context=projection_context(),
    )
    waiter = repository.reserve_operation(
        life_id=LIFE_ID,
        operation_id=operation_id,
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        projection_context=projection_context(),
    )
    assert isinstance(waiter, QuestOperationWaiter)

    assert repository.wait_for_operation(waiter) is False


def test_operation_id_reuse_for_different_command_or_target_conflicts() -> None:
    repository = InMemoryQuestRepository()
    commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )

    with pytest.raises(OperationIdConflictError):
        commit_accept(repository,
            life_id=LIFE_ID,
            quest_id="different",
            provider_id="old-man",
            definition_version=1,
            operation_id=FIRST_OPERATION,
            accepted_at=NOW,
        )
    with pytest.raises(OperationIdConflictError):
        commit_complete(repository,
            life_id=LIFE_ID,
            quest_id="first-steps",
            provider_id="old-man",
            operation_id=FIRST_OPERATION,
            completed_at=NOW,
        )

    assert repository.get_quest_revision(LIFE_ID) == 1


def test_operation_id_reuse_for_different_provider_conflicts() -> None:
    repository = InMemoryQuestRepository()
    commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )

    with pytest.raises(OperationIdConflictError):
        commit_accept(repository,
            life_id=LIFE_ID,
            quest_id="first-steps",
            provider_id="other-provider",
            definition_version=1,
            operation_id=FIRST_OPERATION,
            accepted_at=NOW,
        )


def test_concurrent_accept_has_exactly_one_change() -> None:
    repository = InMemoryQuestRepository()

    def accept(index: int):
        return commit_accept(repository,
            life_id=LIFE_ID,
            quest_id="first-steps",
            provider_id="old-man",
            definition_version=1,
            operation_id=UUID(int=300 + index),
            accepted_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(accept, range(2)))

    assert [result.changed for result in results].count(True) == 1
    assert repository.get_quest_revision(LIFE_ID) == 1


def test_concurrent_completion_has_exactly_one_change() -> None:
    repository = InMemoryQuestRepository()
    commit_accept(repository,
        life_id=LIFE_ID,
        quest_id="first-steps",
        provider_id="old-man",
        definition_version=1,
        operation_id=FIRST_OPERATION,
        accepted_at=NOW,
    )

    def complete(index: int):
        return commit_complete(repository,
            life_id=LIFE_ID,
            quest_id="first-steps",
            provider_id="old-man",
            operation_id=UUID(int=400 + index),
            completed_at=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(complete, range(2)))

    assert [result.changed for result in results].count(True) == 1
    assert repository.get_quest_revision(LIFE_ID) == 2
