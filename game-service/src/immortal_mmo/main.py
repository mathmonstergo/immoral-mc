from fastapi import FastAPI

from immortal_mmo.api.errors import domain_error_handler
from immortal_mmo.api.v1.router import api_router
from immortal_mmo.core.errors import DomainError
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.repository import InMemoryQuestRepository
from immortal_mmo.quest.service import QuestService


def create_app(
    player_service: PlayerService | None = None,
    quest_service: QuestService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Immortal MMO Game Service",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    shared_player_service = player_service or PlayerService()
    app.state.player_service = shared_player_service
    app.state.quest_service = quest_service or QuestService(
        shared_player_service,
        InMemoryQuestRepository(),
    )
    app.add_exception_handler(DomainError, domain_error_handler)
    app.include_router(api_router)
    return app


app = create_app()
