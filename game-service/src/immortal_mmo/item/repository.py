from collections.abc import Collection
from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.item.models import (
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemResourceEntry,
    ItemStack,
)


class ItemRepository(Protocol):
    async def get_stack(self, life_id: UUID, item_code: str, *, for_update: bool) -> ItemStack: ...

    async def get_stacks(
        self,
        life_id: UUID,
        item_codes: Collection[str],
        *,
        for_update: bool,
    ) -> dict[str, ItemStack]: ...

    async def adjust(
        self,
        *,
        life_id: UUID,
        item_code: str,
        delta_quantity: int,
        operation_id: UUID,
        occurred_at: datetime,
    ) -> ItemResourceEntry: ...

    async def consume(
        self,
        *,
        life_id: UUID,
        item_code: str,
        quantity: int,
        operation_id: UUID,
        entry_type: ItemConsumptionType,
        session_id: UUID | None,
        occurred_at: datetime,
    ) -> ItemResourceEntry: ...

    async def consume_many(
        self,
        *,
        life_id: UUID,
        consumptions: Collection[ItemConsumptionRequest],
    ) -> tuple[ItemResourceEntry, ...]: ...
