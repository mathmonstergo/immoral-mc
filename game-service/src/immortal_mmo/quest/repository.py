from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from threading import Event, Lock
from time import monotonic as system_monotonic
from types import MappingProxyType
from typing import Protocol
from uuid import UUID, uuid4


class QuestProgressStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class QuestOperationCommand(StrEnum):
    ACCEPT = "accept"
    TURN_IN = "turn_in"


class OperationIdConflictError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class QuestProgress:
    life_id: UUID
    quest_id: str
    definition_version: int
    status: QuestProgressStatus
    accepted_at: datetime
    completed_at: datetime | None
    revision: int


@dataclass(frozen=True, slots=True)
class QuestProgressSnapshot:
    progresses: Mapping[str, QuestProgress]
    quest_revision: int


@dataclass(frozen=True, slots=True)
class QuestOperationProjectionContext:
    account_id: UUID
    life_id: UUID
    revision: int
    spirit_root_present: bool


@dataclass(frozen=True, slots=True)
class FrozenQuestDomainError:
    status_code: int
    code: str
    message: str
    retryable: bool


@dataclass(frozen=True, slots=True)
class QuestOperationState:
    life_id: UUID
    operation_id: UUID
    command: QuestOperationCommand
    quest_id: str
    provider_id: str
    projection_context: QuestOperationProjectionContext
    changed: bool | None = None
    progress: QuestProgress | None = None
    snapshot: QuestProgressSnapshot | None = None

    @property
    def mutation_attached(self) -> bool:
        return self.changed is not None and self.progress is not None and self.snapshot is not None


@dataclass(frozen=True, slots=True)
class QuestFinalizedOperation:
    state: QuestOperationState
    frozen_response_json: str

    def __post_init__(self) -> None:
        if not self.state.mutation_attached:
            raise ValueError("Successful quest operation requires attached mutation state")
        if not self.frozen_response_json:
            raise ValueError("Finalized quest operation requires a frozen response")

    @property
    def operation_id(self) -> UUID:
        return self.state.operation_id

    @property
    def command(self) -> QuestOperationCommand:
        return self.state.command

    @property
    def provider_id(self) -> str:
        return self.state.provider_id

    @property
    def changed(self) -> bool:
        assert self.state.changed is not None
        return self.state.changed

    @property
    def progress(self) -> QuestProgress:
        assert self.state.progress is not None
        return self.state.progress

    @property
    def snapshot(self) -> QuestProgressSnapshot:
        assert self.state.snapshot is not None
        return self.state.snapshot

    @property
    def quest_revision(self) -> int:
        return self.snapshot.quest_revision


@dataclass(frozen=True, slots=True)
class QuestFinalizedFailure:
    state: QuestOperationState
    error: FrozenQuestDomainError

    def __post_init__(self) -> None:
        if self.state.mutation_attached:
            raise ValueError("Failed quest operation cannot contain mutation state")


@dataclass(frozen=True, slots=True)
class QuestOperationOwner:
    state: QuestOperationState
    owner_token: UUID
    lease_expires_at: float


@dataclass(frozen=True, slots=True)
class QuestOperationWaiter:
    life_id: UUID
    operation_id: UUID
    finished: Event
    wait_timeout_seconds: float


type QuestFinalizedResult = QuestFinalizedOperation | QuestFinalizedFailure
type QuestOperationAttempt = QuestFinalizedResult | QuestOperationOwner | QuestOperationWaiter


@dataclass(slots=True)
class _PendingOperation:
    state: QuestOperationState
    owner_token: UUID | None
    lease_expires_at: float
    finished: Event


class QuestRepository(Protocol):
    def get_progress_snapshot(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> QuestProgressSnapshot: ...

    def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]: ...

    def get_quest_revision(self, life_id: UUID) -> int: ...

    def reserve_operation(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        projection_context: QuestOperationProjectionContext,
    ) -> QuestOperationAttempt: ...

    def attach_accept_mutation(
        self,
        owner: QuestOperationOwner,
        *,
        definition_version: int,
        accepted_at: datetime,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationOwner: ...

    def attach_complete_mutation(
        self,
        owner: QuestOperationOwner,
        *,
        completed_at: datetime,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationOwner: ...

    def wait_for_operation(self, waiter: QuestOperationWaiter) -> bool: ...

    def finalize_operation(
        self,
        owner: QuestOperationOwner,
        frozen_response_json: str,
    ) -> QuestFinalizedOperation: ...

    def finalize_failure(
        self,
        owner: QuestOperationOwner,
        error: FrozenQuestDomainError,
    ) -> QuestFinalizedFailure: ...

    def release_operation_owner(self, owner: QuestOperationOwner) -> None: ...


class InMemoryQuestRepository:
    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = system_monotonic,
        operation_lease_seconds: float = 2.0,
        operation_wait_seconds: float = 2.0,
    ) -> None:
        if not 0 < operation_lease_seconds <= 2.0:
            raise ValueError("operation_lease_seconds must be between 0 and 2 seconds")
        if not 0 < operation_wait_seconds <= 2.0:
            raise ValueError("operation_wait_seconds must be between 0 and 2 seconds")
        self._progress_by_key: dict[tuple[UUID, str], QuestProgress] = {}
        self._quest_revision_by_life: dict[UUID, int] = {}
        self._operation_by_key: dict[
            tuple[UUID, UUID], _PendingOperation | QuestFinalizedResult
        ] = {}
        self._monotonic = monotonic
        self._operation_lease_seconds = operation_lease_seconds
        self._operation_wait_seconds = operation_wait_seconds
        self._lock = Lock()

    def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]:
        with self._lock:
            return {
                quest_id: progress
                for quest_id in quest_ids
                if (progress := self._progress_by_key.get((life_id, quest_id))) is not None
            }

    def get_progress_snapshot(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> QuestProgressSnapshot:
        with self._lock:
            return self._snapshot_unlocked(life_id, quest_ids)

    def get_quest_revision(self, life_id: UUID) -> int:
        with self._lock:
            return self._quest_revision_by_life.get(life_id, 0)

    def get_operation_result(
        self,
        life_id: UUID,
        operation_id: UUID,
    ) -> QuestFinalizedResult | None:
        with self._lock:
            operation = self._operation_by_key.get((life_id, operation_id))
            return operation if not isinstance(operation, _PendingOperation) else None

    def reserve_operation(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        projection_context: QuestOperationProjectionContext,
    ) -> QuestOperationAttempt:
        with self._lock:
            existing = self._claim_existing_unlocked(
                life_id,
                operation_id,
                command,
                quest_id,
                provider_id,
            )
            if existing is not None:
                return existing
            state = QuestOperationState(
                life_id=life_id,
                operation_id=operation_id,
                command=command,
                quest_id=quest_id,
                provider_id=provider_id,
                projection_context=projection_context,
            )
            return self._create_pending_unlocked(state)

    def claim_operation(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
    ) -> QuestOperationAttempt | None:
        with self._lock:
            return self._claim_existing_unlocked(
                life_id,
                operation_id,
                command,
                quest_id,
                provider_id,
            )

    def accept(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        provider_id: str,
        definition_version: int,
        operation_id: UUID,
        accepted_at: datetime,
        projection_context: QuestOperationProjectionContext | None = None,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationAttempt:
        context = projection_context or QuestOperationProjectionContext(
            account_id=UUID(int=0),
            life_id=life_id,
            revision=0,
            spirit_root_present=False,
        )
        attempt = self.reserve_operation(
            life_id=life_id,
            operation_id=operation_id,
            command=QuestOperationCommand.ACCEPT,
            quest_id=quest_id,
            provider_id=provider_id,
            projection_context=context,
        )
        if isinstance(attempt, QuestOperationOwner) and not attempt.state.mutation_attached:
            return self.attach_accept_mutation(
                attempt,
                definition_version=definition_version,
                accepted_at=accepted_at,
                projection_quest_ids=projection_quest_ids,
            )
        return attempt

    def complete(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
        completed_at: datetime,
        projection_context: QuestOperationProjectionContext | None = None,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationAttempt:
        context = projection_context or QuestOperationProjectionContext(
            account_id=UUID(int=0),
            life_id=life_id,
            revision=0,
            spirit_root_present=False,
        )
        attempt = self.reserve_operation(
            life_id=life_id,
            operation_id=operation_id,
            command=QuestOperationCommand.TURN_IN,
            quest_id=quest_id,
            provider_id=provider_id,
            projection_context=context,
        )
        if isinstance(attempt, QuestOperationOwner) and not attempt.state.mutation_attached:
            return self.attach_complete_mutation(
                attempt,
                completed_at=completed_at,
                projection_quest_ids=projection_quest_ids,
            )
        return attempt

    def attach_accept_mutation(
        self,
        owner: QuestOperationOwner,
        *,
        definition_version: int,
        accepted_at: datetime,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationOwner:
        with self._lock:
            pending = self._pending_for_owner_unlocked(owner)
            if pending.state.mutation_attached:
                return self._owner_from_pending_unlocked(pending)
            key = (pending.state.life_id, pending.state.quest_id)
            progress = self._progress_by_key.get(key)
            changed = progress is None
            if progress is None:
                revision = self._next_revision(pending.state.life_id)
                progress = QuestProgress(
                    life_id=pending.state.life_id,
                    quest_id=pending.state.quest_id,
                    definition_version=definition_version,
                    status=QuestProgressStatus.ACTIVE,
                    accepted_at=accepted_at,
                    completed_at=None,
                    revision=revision,
                )
                self._progress_by_key[key] = progress
            return self._attach_mutation_unlocked(
                pending,
                changed,
                progress,
                projection_quest_ids,
            )

    def attach_complete_mutation(
        self,
        owner: QuestOperationOwner,
        *,
        completed_at: datetime,
        projection_quest_ids: Collection[str] | None = None,
    ) -> QuestOperationOwner:
        with self._lock:
            pending = self._pending_for_owner_unlocked(owner)
            if pending.state.mutation_attached:
                return self._owner_from_pending_unlocked(pending)
            key = (pending.state.life_id, pending.state.quest_id)
            progress = self._progress_by_key[key]
            changed = progress.status is QuestProgressStatus.ACTIVE
            if changed:
                revision = self._next_revision(pending.state.life_id)
                progress = replace(
                    progress,
                    status=QuestProgressStatus.COMPLETED,
                    completed_at=completed_at,
                    revision=revision,
                )
                self._progress_by_key[key] = progress
            return self._attach_mutation_unlocked(
                pending,
                changed,
                progress,
                projection_quest_ids,
            )

    def wait_for_operation(self, waiter: QuestOperationWaiter) -> bool:
        return waiter.finished.wait(timeout=waiter.wait_timeout_seconds)

    def finalize_operation(
        self,
        owner: QuestOperationOwner,
        frozen_response_json: str,
    ) -> QuestFinalizedOperation:
        finalized = QuestFinalizedOperation(
            state=owner.state,
            frozen_response_json=frozen_response_json,
        )
        with self._lock:
            pending = self._pending_for_owner_unlocked(owner)
            self._operation_by_key[(owner.state.life_id, owner.state.operation_id)] = finalized
            pending.finished.set()
            return finalized

    def finalize_failure(
        self,
        owner: QuestOperationOwner,
        error: FrozenQuestDomainError,
    ) -> QuestFinalizedFailure:
        finalized = QuestFinalizedFailure(state=owner.state, error=error)
        with self._lock:
            pending = self._pending_for_owner_unlocked(owner)
            self._operation_by_key[(owner.state.life_id, owner.state.operation_id)] = finalized
            pending.finished.set()
            return finalized

    def release_operation_owner(self, owner: QuestOperationOwner) -> None:
        with self._lock:
            pending = self._operation_by_key.get((owner.state.life_id, owner.state.operation_id))
            if not isinstance(pending, _PendingOperation):
                return
            if pending.owner_token != owner.owner_token:
                return
            previous_waiters = pending.finished
            pending.owner_token = None
            pending.lease_expires_at = 0.0
            pending.finished = Event()
            previous_waiters.set()

    def _create_pending_unlocked(self, state: QuestOperationState) -> QuestOperationOwner:
        owner_token = uuid4()
        lease_expires_at = self._monotonic() + self._operation_lease_seconds
        pending = _PendingOperation(
            state=state,
            owner_token=owner_token,
            lease_expires_at=lease_expires_at,
            finished=Event(),
        )
        self._operation_by_key[(state.life_id, state.operation_id)] = pending
        return QuestOperationOwner(state, owner_token, lease_expires_at)

    def _claim_existing_unlocked(
        self,
        life_id: UUID,
        operation_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
    ) -> QuestOperationAttempt | None:
        existing = self._operation_by_key.get((life_id, operation_id))
        if existing is None:
            return None
        state = existing.state
        if (
            state.command is not command
            or state.quest_id != quest_id
            or state.provider_id != provider_id
        ):
            raise OperationIdConflictError
        if not isinstance(existing, _PendingOperation):
            return existing

        now = self._monotonic()
        if existing.owner_token is not None and now < existing.lease_expires_at:
            remaining = existing.lease_expires_at - now
            return QuestOperationWaiter(
                life_id,
                operation_id,
                existing.finished,
                min(remaining, self._operation_wait_seconds),
            )
        if existing.owner_token is not None:
            previous_waiters = existing.finished
            existing.finished = Event()
            previous_waiters.set()
        existing.owner_token = uuid4()
        existing.lease_expires_at = now + self._operation_lease_seconds
        return self._owner_from_pending_unlocked(existing)

    def _pending_for_owner_unlocked(self, owner: QuestOperationOwner) -> _PendingOperation:
        pending = self._operation_by_key.get((owner.state.life_id, owner.state.operation_id))
        if not isinstance(pending, _PendingOperation):
            raise RuntimeError("Quest operation is not pending")
        if (
            pending.owner_token != owner.owner_token
            or pending.state != owner.state
            or self._monotonic() >= pending.lease_expires_at
        ):
            raise RuntimeError("Quest operation ownership was lost")
        return pending

    def _owner_from_pending_unlocked(self, pending: _PendingOperation) -> QuestOperationOwner:
        assert pending.owner_token is not None
        return QuestOperationOwner(
            state=pending.state,
            owner_token=pending.owner_token,
            lease_expires_at=pending.lease_expires_at,
        )

    def _attach_mutation_unlocked(
        self,
        pending: _PendingOperation,
        changed: bool,
        progress: QuestProgress,
        projection_quest_ids: Collection[str] | None,
    ) -> QuestOperationOwner:
        pending.state = replace(
            pending.state,
            changed=changed,
            progress=progress,
            snapshot=self._snapshot_unlocked(pending.state.life_id, projection_quest_ids),
        )
        pending.lease_expires_at = self._monotonic() + self._operation_lease_seconds
        return self._owner_from_pending_unlocked(pending)

    def _next_revision(self, life_id: UUID) -> int:
        revision = self._quest_revision_by_life.get(life_id, 0) + 1
        self._quest_revision_by_life[life_id] = revision
        return revision

    def _snapshot_unlocked(
        self,
        life_id: UUID,
        quest_ids: Collection[str] | None,
    ) -> QuestProgressSnapshot:
        if quest_ids is None:
            progresses = {
                quest_id: progress
                for (progress_life_id, quest_id), progress in self._progress_by_key.items()
                if progress_life_id == life_id
            }
        else:
            progresses = {
                quest_id: progress
                for quest_id in quest_ids
                if (progress := self._progress_by_key.get((life_id, quest_id))) is not None
            }
        return QuestProgressSnapshot(
            progresses=MappingProxyType(progresses),
            quest_revision=self._quest_revision_by_life.get(life_id, 0),
        )
