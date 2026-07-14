from uuid import UUID

from fastapi import APIRouter, Depends, Request

from immortal_mmo.player.schemas import (
    PlayerLoginRequest,
    PlayerLoginResponse,
    SpiritRootDetectionResponse,
)
from immortal_mmo.player.service import PlayerService

router = APIRouter(prefix="/api/v1/players", tags=["players"])


async def get_player_service(request: Request) -> PlayerService:
    return request.app.state.player_service


player_service_dependency = Depends(get_player_service)


@router.post("/login", response_model=PlayerLoginResponse)
async def login_player(
    request: PlayerLoginRequest,
    service: PlayerService = player_service_dependency,
) -> PlayerLoginResponse:
    return await service.login(
        minecraft_uuid=request.minecraft_uuid,
        player_name=request.player_name,
    )


@router.post("/{account_id}/current-life/spirit-root", response_model=SpiritRootDetectionResponse)
async def detect_current_life_spirit_root(
    account_id: UUID,
    service: PlayerService = player_service_dependency,
) -> SpiritRootDetectionResponse:
    return await service.detect_current_life_spirit_root(account_id)
