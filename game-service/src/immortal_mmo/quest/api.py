from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from immortal_mmo.quest.schemas import (
    QuestInteractionState,
    QuestInteractionStateRequest,
    QuestMutationRequest,
    QuestMutationResult,
    QuestProviderCatalog,
)
from immortal_mmo.quest.service import QuestService

router = APIRouter(prefix="/api/v1/players", tags=["quests"])
catalog_router = APIRouter(prefix="/api/v1", tags=["quests"])


def get_quest_service(request: Request) -> QuestService:
    return request.app.state.quest_service


quest_service_dependency = Depends(get_quest_service)
idempotency_key_header = Header(alias="Idempotency-Key")


@catalog_router.get(
    "/quest-providers",
    response_model=QuestProviderCatalog,
)
def get_quest_provider_catalog(
    service: QuestService = quest_service_dependency,
) -> QuestProviderCatalog:
    return service.get_provider_catalog()


@router.post(
    "/{account_id}/current-life/quest-interaction-state",
    response_model=QuestInteractionState,
)
def get_quest_interaction_state(
    account_id: UUID,
    body: QuestInteractionStateRequest,
    service: QuestService = quest_service_dependency,
) -> QuestInteractionState:
    return service.get_interaction_state(account_id, body.provider_ids)


@router.put(
    "/{account_id}/current-life/quests/{quest_id}/accept",
    response_model=QuestMutationResult,
)
def accept_quest(
    account_id: UUID,
    quest_id: str,
    body: QuestMutationRequest,
    idempotency_key: Annotated[UUID, idempotency_key_header],
    service: QuestService = quest_service_dependency,
) -> QuestMutationResult:
    return service.accept(account_id, quest_id, body.provider_id, idempotency_key)


@router.put(
    "/{account_id}/current-life/quests/{quest_id}/turn-in",
    response_model=QuestMutationResult,
)
def turn_in_quest(
    account_id: UUID,
    quest_id: str,
    body: QuestMutationRequest,
    idempotency_key: Annotated[UUID, idempotency_key_header],
    service: QuestService = quest_service_dependency,
) -> QuestMutationResult:
    return service.turn_in(account_id, quest_id, body.provider_id, idempotency_key)
