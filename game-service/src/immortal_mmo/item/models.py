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


class ItemInstanceStatus(StrEnum):
    PENDING_DELIVERY = "pending_delivery"
    OWNED = "owned"
    CONSUMED = "consumed"


class ItemLocation(StrEnum):
    INVENTORY = "inventory"
    STORAGE = "storage"


@dataclass(frozen=True, slots=True)
class ItemInstance:
    item_instance_id: UUID
    life_id: UUID
    item_code: str
    definition_version: int
    technique_id: str | None
    issuance_id: UUID
    issuance_ordinal: int
    quest_reward_grant_id: UUID | None
    status: ItemInstanceStatus
    created_at: datetime
    delivered_at: datetime | None
    consumed_at: datetime | None
    location: ItemLocation | None = None

    def __post_init__(self) -> None:
        if self.definition_version <= 0:
            raise ValueError("Item definition version must be positive")
        if self.issuance_ordinal < 0:
            raise ValueError("Item issuance ordinal must be non-negative")
        if self.status is ItemInstanceStatus.PENDING_DELIVERY:
            if (
                self.location is not None
                or self.delivered_at is not None
                or self.consumed_at is not None
            ):
                raise ValueError("Pending item state is invalid")
            return
        if self.status is ItemInstanceStatus.OWNED:
            if (
                self.location is None
                or self.delivered_at is None
                or self.consumed_at is not None
            ):
                raise ValueError("Owned item state is invalid")
            return
        if self.location is not None or self.consumed_at is None:
            raise ValueError("Consumed item state is invalid")


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
