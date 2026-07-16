from fastapi import APIRouter, Depends, Request

from immortal_mmo.api.v1.health import (
    HealthResponse,
    ReadinessCheck,
    ReadyResponse,
    ServiceNotReadyError,
    get_health,
)
from immortal_mmo.combat.api import router as combat_router
from immortal_mmo.cultivation.api import router as cultivation_router
from immortal_mmo.player.api import router as player_router
from immortal_mmo.quest.api import catalog_router as quest_catalog_router
from immortal_mmo.quest.api import router as quest_router

api_router = APIRouter()
api_router.include_router(player_router)
api_router.include_router(quest_catalog_router)
api_router.include_router(quest_router)
api_router.include_router(combat_router)
api_router.include_router(cultivation_router)


@api_router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return get_health()


async def get_readiness_check(request: Request) -> ReadinessCheck:
    return request.app.state.readiness_check


readiness_dependency = Depends(get_readiness_check)


@api_router.get("/ready", response_model=ReadyResponse)
async def ready(
    readiness_check: ReadinessCheck = readiness_dependency,
) -> ReadyResponse:
    result = await readiness_check()
    if not result.ready or result.migration_revision is None:
        raise ServiceNotReadyError
    return ReadyResponse(
        status="ready",
        migration_revision=result.migration_revision,
    )
