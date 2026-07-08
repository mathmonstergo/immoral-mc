from fastapi import APIRouter

from immortal_mmo.api.v1.health import HealthResponse, get_health
from immortal_mmo.player.api import router as player_router

api_router = APIRouter()
api_router.include_router(player_router)


@api_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return get_health()
