from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class StorageMoveKind(StrEnum):
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    MOVE = "move"


@dataclass(frozen=True, slots=True)
class StorageContainer:
    life_id: UUID
    area_id: str
    page_count: int
    item_slots_per_page: int
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StorageSlot:
    life_id: UUID
    area_id: str
    page: int
    slot: int
    item_instance_id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StorageOperation:
    operation_id: UUID
    life_id: UUID
    area_id: str
    move_kind: StorageMoveKind
    item_instance_id: UUID
    expected_revision: int
    resulting_revision: int
    source_page: int | None
    source_slot: int | None
    destination_page: int | None
    destination_slot: int | None
    view_page: int
    request_fingerprint: str
    response_body: bytes
    created_at: datetime
