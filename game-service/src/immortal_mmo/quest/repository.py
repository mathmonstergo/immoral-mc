from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class QuestProgressStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class QuestOperationCommand(StrEnum):
    ACCEPT = "accept"
    TURN_IN = "turn_in"


class QuestOperationState(StrEnum):
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    DOMAIN_FAILED = "domain_failed"


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
class StoredQuestOperation:
    operation_id: UUID
    account_id: UUID
    life_id: UUID
    command: QuestOperationCommand
    quest_id: str
    provider_id: str
    request_fingerprint: str
    state: QuestOperationState
    changed: bool | None
    response_status: int | None
    response_content_type: str | None
    response_body: bytes | None
    response_contract_version: int | None
    created_at: datetime
    finalized_at: datetime | None


@dataclass(frozen=True, slots=True)
class FrozenHttpResponse:
    status_code: int
    content_type: str
    body: bytes
    contract_version: int


class QuestRepository(Protocol):
    async def get_operation(self, operation_id: UUID) -> StoredQuestOperation | None: ...

    async def reserve_operation(self, operation: StoredQuestOperation) -> bool: ...

    async def finalize_operation(
        self,
        operation_id: UUID,
        *,
        state: QuestOperationState,
        changed: bool,
        response_status: int,
        response_content_type: str,
        response_body: bytes,
        response_contract_version: int,
        finalized_at: datetime,
    ) -> StoredQuestOperation: ...

    async def get_quest_revision(self, life_id: UUID, *, for_update: bool) -> int: ...

    async def increment_quest_revision(self, life_id: UUID) -> int: ...

    async def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]: ...

    async def get_progress(self, life_id: UUID, quest_id: str) -> QuestProgress | None: ...

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool: ...

    async def complete_progress_if_active(
        self,
        life_id: UUID,
        quest_id: str,
        *,
        completed_at: datetime,
        revision: int,
    ) -> bool: ...
