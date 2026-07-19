from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from immortal_mmo.quest.models import QuestRewardType


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
class QuestObjectiveProgress:
    life_id: UUID
    quest_id: str
    objective_id: str
    definition_version: int
    objective_type: str
    target_id: str
    required_value: int
    current_value: int
    updated_at: datetime


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


@dataclass(frozen=True, slots=True)
class QuestRewardGrant:
    grant_id: UUID
    life_id: UUID
    operation_id: UUID
    quest_id: str
    reward_id: str
    reward_type: QuestRewardType
    item_code: str | None
    configured_amount: int
    applied_amount: int
    pending_amount: int
    status: str
    created_at: datetime


class QuestRepository(Protocol):
    async def insert_reward_grant(self, grant: QuestRewardGrant) -> None: ...

    async def get_reward_grants(
        self,
        operation_id: UUID,
    ) -> tuple[QuestRewardGrant, ...]: ...

    async def get_reward_grant(self, grant_id: UUID) -> QuestRewardGrant | None: ...

    async def update_reward_grant_progress(
        self,
        *,
        grant_id: UUID,
        pending_amount: int,
    ) -> QuestRewardGrant: ...

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

    async def get_objective_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[tuple[str, str], QuestObjectiveProgress]: ...

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool: ...

    async def insert_objective_progresses(
        self,
        progresses: Collection[QuestObjectiveProgress],
    ) -> None: ...

    async def increment_objective_progress(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        objective_id: str,
        required_value: int,
        updated_at: datetime,
    ) -> int | None: ...

    async def increment_objective_progresses(
        self,
        *,
        life_id: UUID,
        objectives: Collection[tuple[str, str]],
        updated_at: datetime,
    ) -> dict[tuple[str, str], int]: ...

    async def complete_progress_if_active(
        self,
        life_id: UUID,
        quest_id: str,
        *,
        completed_at: datetime,
        revision: int,
    ) -> bool: ...
