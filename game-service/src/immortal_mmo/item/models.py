from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class ItemRepositoryError(RuntimeError):
    """Base failure for authoritative life item storage."""


class InsufficientItemQuantity(ItemRepositoryError):
    """Raised when an item debit exceeds the locked stack quantity."""


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
