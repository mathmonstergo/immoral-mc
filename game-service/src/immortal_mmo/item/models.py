from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ItemRepositoryError(RuntimeError):
    """Base failure for authoritative life item storage."""


class InsufficientItemQuantity(ItemRepositoryError):
    """Raised when an item debit exceeds the locked stack quantity."""


class ItemOperationConflict(ItemRepositoryError):
    """Raised when an item operation ID is reused with different immutable facts."""


class ItemConsumptionType(StrEnum):
    BREAKTHROUGH = "breakthrough_consumption"
    QUEST_DELIVERY = "quest_delivery"


@dataclass(frozen=True, slots=True)
class ItemConsumptionRequest:
    item_code: str
    quantity: int
    operation_id: UUID
    entry_type: ItemConsumptionType
    session_id: UUID | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ItemStack:
    life_id: UUID
    item_code: str
    quantity: int
    revision: int


@dataclass(frozen=True, slots=True)
class ItemResourceEntry:
    entry_id: UUID
    life_id: UUID
    item_code: str
    operation_id: UUID
    session_id: UUID | None
    entry_type: str
    delta_quantity: int
    balance_after: int
    created_at: datetime
