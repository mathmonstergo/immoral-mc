from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from immortal_mmo.cultivation.schemas import (
    BreakthroughSnapshotResponse,
    CultivationSnapshotResponse,
    ItemAdjustmentRequest,
    ItemAdjustmentResponse,
    SeclusionSnapshotResponse,
    StartBreakthroughRequest,
    StartSeclusionRequest,
    TechniqueMutationResponse,
    TechniqueSnapshotResponse,
    TransferTechniqueRequest,
)
from immortal_mmo.cultivation.service import CultivationService

router = APIRouter(prefix="/api/v1/players", tags=["cultivation"])


async def get_cultivation_service(request: Request) -> CultivationService:
    return request.app.state.cultivation_service


cultivation_service_dependency = Depends(get_cultivation_service)
idempotency_key_header = Header(alias="Idempotency-Key")


@router.get(
    "/{account_id}/current-life/cultivation",
    response_model=CultivationSnapshotResponse,
)
async def current_life_cultivation(
    account_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> CultivationSnapshotResponse:
    return await service.current_life_snapshot(account_id)


@router.get(
    "/{account_id}/current-life/cultivation/techniques",
    response_model=list[TechniqueSnapshotResponse],
)
async def list_techniques(
    account_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> tuple[TechniqueSnapshotResponse, ...]:
    return await service.list_techniques(account_id)


@router.post(
    "/{account_id}/current-life/cultivation/techniques/{life_technique_id}/abandon",
    response_model=TechniqueMutationResponse,
)
async def abandon_technique(
    account_id: UUID,
    life_technique_id: UUID,
    idempotency_key: UUID = idempotency_key_header,
    service: CultivationService = cultivation_service_dependency,
) -> TechniqueMutationResponse:
    return await service.abandon_technique(
        account_id=account_id,
        life_technique_id=life_technique_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{account_id}/current-life/cultivation/techniques/{life_technique_id}/transfer",
    response_model=TechniqueMutationResponse,
)
async def transfer_technique(
    account_id: UUID,
    life_technique_id: UUID,
    body: TransferTechniqueRequest,
    idempotency_key: UUID = idempotency_key_header,
    service: CultivationService = cultivation_service_dependency,
) -> TechniqueMutationResponse:
    return await service.transfer_technique(
        account_id=account_id,
        source_technique_id=life_technique_id,
        target_technique_id=body.target_technique_id,
        transfer_profile_id=body.transfer_profile_id,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{account_id}/current-life/items/adjustments",
    response_model=ItemAdjustmentResponse,
)
async def adjust_item(
    account_id: UUID,
    body: ItemAdjustmentRequest,
    idempotency_key: UUID = idempotency_key_header,
    service: CultivationService = cultivation_service_dependency,
) -> ItemAdjustmentResponse:
    return await service.adjust_item(
        account_id=account_id,
        item_code=body.item_code,
        delta_quantity=body.delta_quantity,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/{account_id}/current-life/cultivation/breakthroughs",
    response_model=BreakthroughSnapshotResponse,
)
async def start_breakthrough(
    account_id: UUID,
    body: StartBreakthroughRequest,
    idempotency_key: UUID = idempotency_key_header,
    service: CultivationService = cultivation_service_dependency,
) -> BreakthroughSnapshotResponse:
    return await service.start_breakthrough(
        account_id=account_id,
        pill_count=body.pill_count,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{account_id}/current-life/cultivation/breakthroughs/{session_id}",
    response_model=BreakthroughSnapshotResponse,
)
async def breakthrough_status(
    account_id: UUID,
    session_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> BreakthroughSnapshotResponse:
    return await service.breakthrough_status(
        account_id=account_id,
        session_id=session_id,
    )


@router.post(
    "/{account_id}/current-life/cultivation/breakthroughs/{session_id}/settle",
    response_model=BreakthroughSnapshotResponse,
)
async def settle_breakthrough(
    account_id: UUID,
    session_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> BreakthroughSnapshotResponse:
    return await service.settle_breakthrough(
        account_id=account_id,
        session_id=session_id,
    )


@router.post(
    "/{account_id}/current-life/cultivation/seclusions",
    response_model=SeclusionSnapshotResponse,
)
async def start_seclusion(
    account_id: UUID,
    body: StartSeclusionRequest,
    idempotency_key: UUID = idempotency_key_header,
    service: CultivationService = cultivation_service_dependency,
) -> SeclusionSnapshotResponse:
    return await service.start_seclusion(
        account_id=account_id,
        area_id=body.area_id,
        technique_ids=tuple(body.technique_ids),
        idempotency_key=idempotency_key,
    )


@router.get(
    "/{account_id}/current-life/cultivation/seclusions/{session_id}",
    response_model=SeclusionSnapshotResponse,
)
async def seclusion_status(
    account_id: UUID,
    session_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> SeclusionSnapshotResponse:
    return await service.seclusion_status(account_id=account_id, session_id=session_id)


@router.post(
    "/{account_id}/current-life/cultivation/seclusions/{session_id}/settle",
    response_model=SeclusionSnapshotResponse,
)
async def settle_seclusion(
    account_id: UUID,
    session_id: UUID,
    service: CultivationService = cultivation_service_dependency,
) -> SeclusionSnapshotResponse:
    return await service.settle_seclusion(account_id=account_id, session_id=session_id)
