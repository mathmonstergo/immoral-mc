from collections.abc import Collection
from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.item.models import (
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemInstance,
    ItemLocation,
    ItemResourceEntry,
    ItemStack,
)


class ItemRepository(Protocol):
    async def get_pending_instances(self, life_id: UUID) -> tuple[ItemInstance, ...]: ...

    async def count_pending_quest_reward_instances(
        self,
        quest_reward_grant_id: UUID,
    ) -> int: ...

    async def create_pending_instances(
        self,
        *,
        life_id: UUID,
        issuance_id: UUID,
        quest_reward_grant_id: UUID | None,
        item_code: str,
        definition_version: int,
        technique_id: str | None,
        item_instance_ids: Collection[UUID],
        created_at: datetime,
    ) -> tuple[ItemInstance, ...]: ...

    async def get_instance(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> ItemInstance | None: ...

    async def get_instances(
        self,
        item_instance_ids: Collection[UUID],
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]: ...

    async def get_inventory_instances(
        self,
        life_id: UUID,
        item_codes: Collection[str] = (),
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]: ...

    async def set_instance_location(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        expected: ItemLocation,
        destination: ItemLocation,
    ) -> ItemInstance: ...

    async def confirm_delivery(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        delivered_at: datetime,
    ) -> ItemInstance: ...

    async def consume_instance(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        consumed_at: datetime,
    ) -> ItemInstance: ...

    async def consume_inventory_instances(
        self,
        *,
        life_id: UUID,
        item_instance_ids: Collection[UUID],
        consumed_at: datetime,
    ) -> tuple[ItemInstance, ...]: ...

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
