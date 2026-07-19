from uuid import UUID

from fastapi import APIRouter, Depends, Request

from immortal_mmo.item.schemas import (
    InventoryItemInstancesResponse,
    ItemDeliveryConfirmationResponse,
    PendingItemDeliveriesResponse,
)
from immortal_mmo.item.service import ItemService

router = APIRouter(prefix="/api/v1/players", tags=["items"])


async def get_item_service(request: Request) -> ItemService:
    return request.app.state.item_service


item_service_dependency = Depends(get_item_service)


@router.get(
    "/{account_id}/current-life/items/pending-deliveries",
    response_model=PendingItemDeliveriesResponse,
)
async def pending_item_deliveries(
    account_id: UUID,
    service: ItemService = item_service_dependency,
) -> PendingItemDeliveriesResponse:
    return await service.pending_deliveries(account_id)


@router.get(
    "/{account_id}/current-life/items/inventory",
    response_model=InventoryItemInstancesResponse,
)
async def inventory_item_instances(
    account_id: UUID,
    service: ItemService = item_service_dependency,
) -> InventoryItemInstancesResponse:
    return await service.inventory_instances(account_id)


@router.put(
    "/{account_id}/current-life/items/{item_instance_id}/delivery-confirmation",
    response_model=ItemDeliveryConfirmationResponse,
)
async def confirm_item_delivery(
    account_id: UUID,
    item_instance_id: UUID,
    service: ItemService = item_service_dependency,
) -> ItemDeliveryConfirmationResponse:
    return await service.confirm_delivery(
        account_id=account_id,
        item_instance_id=item_instance_id,
    )
