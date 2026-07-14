from fastapi import FastAPI

from immortal_mmo.api.errors import domain_error_handler
from immortal_mmo.api.v1.router import api_router
from immortal_mmo.core.errors import DomainError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.service import QuestService


def create_app(*, uow_factory: UnitOfWorkFactory) -> FastAPI:
    app = FastAPI(
        title="Immortal MMO Game Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.player_service = PlayerService(uow_factory)
    app.state.quest_service = QuestService(uow_factory)
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)
    return app
