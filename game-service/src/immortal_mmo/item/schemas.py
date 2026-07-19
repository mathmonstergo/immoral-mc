from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class ItemInstanceProjection(BaseModel):
    contract_version: Literal[1] = 1
    item_instance_id: UUID
    item_code: str
    definition_version: int
    technique_id: str | None
    status: Literal["pending_delivery", "owned", "consumed"]
    location: Literal["inventory", "storage"] | None


class PendingItemDeliveriesResponse(BaseModel):
    contract_version: Literal[1] = 1
    life_id: UUID
    items: list[ItemInstanceProjection]


class InventoryItemInstancesResponse(BaseModel):
    contract_version: Literal[1] = 1
    life_id: UUID
    items: list[ItemInstanceProjection]


class ItemDeliveryConfirmationResponse(BaseModel):
    contract_version: Literal[1] = 1
    item: ItemInstanceProjection
