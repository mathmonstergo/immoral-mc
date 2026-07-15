from fastapi import APIRouter, Depends, Request

from immortal_mmo.combat.schemas import CombatKillBatchRequest, CombatKillBatchResponse
from immortal_mmo.combat.service import CombatRewardService

router = APIRouter(prefix="/api/v1/combat", tags=["combat"])


async def get_combat_service(request: Request) -> CombatRewardService:
    return request.app.state.combat_service


combat_service_dependency = Depends(get_combat_service)


@router.post(
    "/mythicmob-kills/batch",
    response_model=CombatKillBatchResponse,
)
async def process_mythicmob_kill_batch(
    body: CombatKillBatchRequest,
    service: CombatRewardService = combat_service_dependency,
) -> CombatKillBatchResponse:
    return await service.process_batch(body)
