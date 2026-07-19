from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from immortal_mmo.storage.schemas import (
    StorageMoveRequest,
    StorageMoveResponse,
    StorageSnapshotResponse,
)
from immortal_mmo.storage.service import StorageService

router = APIRouter(prefix="/api/v1/players", tags=["storage"])


async def get_storage_service(request: Request) -> StorageService:
    return request.app.state.storage_service


storage_service_dependency = Depends(get_storage_service)
idempotency_key_header = Header(alias="Idempotency-Key")


@router.get(
    "/{account_id}/current-life/storage/{area_id}",
    response_model=StorageSnapshotResponse,
)
async def storage_snapshot(
    account_id: UUID,
    area_id: str,
    page: Annotated[int, Query(ge=1)] = 1,
    service: StorageService = storage_service_dependency,
) -> StorageSnapshotResponse:
    return await service.snapshot(
        account_id=account_id,
        area_id=area_id,
        page=page,
    )


@router.post(
    "/{account_id}/current-life/storage/{area_id}/moves",
    response_model=StorageMoveResponse,
)
async def move_storage_item(
    account_id: UUID,
    area_id: str,
    body: StorageMoveRequest,
    idempotency_key: Annotated[UUID, idempotency_key_header],
    service: StorageService = storage_service_dependency,
) -> StorageMoveResponse:
    return await service.move(
        account_id=account_id,
        area_id=area_id,
        operation_id=idempotency_key,
        request=body,
    )
