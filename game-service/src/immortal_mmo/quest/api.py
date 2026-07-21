from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from starlette.responses import Response

from immortal_mmo.quest.schemas import (
    QuestInteractionState,
    QuestInteractionStateRequest,
    QuestMutationResult,
    QuestProviderCatalog,
    QuestProviderRequest,
    QuestTurnInRequest,
)
from immortal_mmo.quest.service import QuestService

router = APIRouter(prefix="/api/v1/players", tags=["quests"])
catalog_router = APIRouter(prefix="/api/v1", tags=["quests"])


async def get_quest_service(request: Request) -> QuestService:
    return request.app.state.quest_service


quest_service_dependency = Depends(get_quest_service)
idempotency_key_header = Header(alias="Idempotency-Key")


@catalog_router.get(
    "/quest-providers",
    response_model=QuestProviderCatalog,
)
async def get_quest_provider_catalog(
    service: QuestService = quest_service_dependency,
) -> QuestProviderCatalog:
    return await service.get_provider_catalog()


@router.post(
    "/{account_id}/current-life/quest-interaction-state",
    response_model=QuestInteractionState,
)
async def get_quest_interaction_state(
    account_id: UUID,
    body: QuestInteractionStateRequest,
    service: QuestService = quest_service_dependency,
) -> QuestInteractionState:
    return await service.get_interaction_state(account_id, body.provider_ids)


@router.put(
    "/{account_id}/current-life/quests/{quest_id}/accept",
    response_model=QuestMutationResult,
)
async def accept_quest(
    account_id: UUID,
    quest_id: str,
    body: QuestProviderRequest,
    idempotency_key: Annotated[UUID, idempotency_key_header],
    service: QuestService = quest_service_dependency,
) -> Response:
    frozen = await service.accept(
        account_id,
        quest_id,
        body.provider_id,
        idempotency_key,
        expected_life_id=body.expected_life_id,
    )
    return Response(
        content=frozen.body,
        status_code=frozen.status_code,
        media_type=frozen.content_type,
    )


@router.put(
    "/{account_id}/current-life/quests/{quest_id}/turn-in",
    response_model=QuestMutationResult,
)
async def turn_in_quest(
    account_id: UUID,
    quest_id: str,
    body: QuestTurnInRequest,
    idempotency_key: Annotated[UUID, idempotency_key_header],
    service: QuestService = quest_service_dependency,
) -> Response:
    frozen = await service.turn_in(
        account_id,
        quest_id,
        body.provider_id,
        idempotency_key,
        expected_life_id=body.expected_life_id,
        inventory_item_instance_ids=tuple(body.inventory_item_instance_ids),
    )
    return Response(
        content=frozen.body,
        status_code=frozen.status_code,
        media_type=frozen.content_type,
    )
