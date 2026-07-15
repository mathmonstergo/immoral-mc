from fastapi import FastAPI
from starlette.types import Lifespan

from immortal_mmo.api.errors import domain_error_handler
from immortal_mmo.api.v1.health import ReadinessCheck, not_configured_readiness
from immortal_mmo.api.v1.router import api_router
from immortal_mmo.core.errors import DomainError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.service import QuestService


def create_app(
    *,
    uow_factory: UnitOfWorkFactory,
    lifespan: Lifespan[FastAPI] | None = None,
    readiness_check: ReadinessCheck | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Immortal MMO Game Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.player_service = PlayerService(uow_factory)
    app.state.quest_service = QuestService(uow_factory)
    app.state.readiness_check = (
        readiness_check if readiness_check is not None else not_configured_readiness
    )
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)
    return app
