from uuid import UUID

from fastapi import APIRouter, Depends, Request

from immortal_mmo.cultivation.schemas import CultivationSnapshotResponse
from immortal_mmo.cultivation.service import CultivationService

router = APIRouter(prefix="/api/v1/players", tags=["cultivation"])


async def get_cultivation_service(request: Request) -> CultivationService:
    return request.app.state.cultivation_service


cultivation_service_dependency = Depends(get_cultivation_service)


@router.get(
    "/{account_id}/current-life/cultivation",
    response_model=CultivationSnapshotResponse,
)
async def current_life_cultivation(
    account_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> CultivationSnapshotResponse:
    return await service.current_life_snapshot(account_id)
