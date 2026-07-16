from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from immortal_mmo.cultivation.schemas import (
    CultivationSnapshotResponse,
    SeclusionSnapshotResponse,
    StartSeclusionRequest,
    TechniqueMutationResponse,
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
