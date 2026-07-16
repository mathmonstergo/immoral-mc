from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CultivationSnapshotResponse(BaseModel):
    contract_version: Literal[1] = 1
    current_level: int
    realm_name: str
    current_progress: int
    max_exp: int
    realized_total: int
    unrefined_reserve: int
    reserve_cap: int
    revision: int
    progress_full: bool
    reserve_full: bool
    can_advance: bool


class SeclusionSnapshotResponse(BaseModel):
    contract_version: Literal[1] = 1
    session_id: UUID
    status: str
    started_at: datetime
    completes_at: datetime
    cumulative_generated: int
    cumulative_reserve_consumed: int
    cumulative_retained: int


class StartSeclusionRequest(BaseModel):
    area_id: str = Field(min_length=1, max_length=64)
    technique_ids: list[UUID] = Field(min_length=1, max_length=5)


class TechniqueSnapshotResponse(BaseModel):
    contract_version: Literal[1] = 1
    life_technique_id: UUID
    technique_id: str
    display_name: str
    definition_version: int
    group_code: str
    major_realm: str
    invested_amount: int
    max_investment: int
    current_layer: int
    status: str


class TransferTechniqueRequest(BaseModel):
    target_technique_id: UUID
    transfer_profile_id: str = Field(min_length=1, max_length=64)


class TechniqueMutationResponse(BaseModel):
    contract_version: Literal[1] = 1
    operation_id: UUID
    operation_kind: Literal["abandonment", "transfer"]
    source_technique_id: UUID
    target_technique_id: UUID | None
    removed_amount: int
    transferred_amount: int
    destroyed_amount: int
    cultivation: CultivationSnapshotResponse


class StartBreakthroughRequest(BaseModel):
    pill_count: int = Field(ge=1, le=10)


class BreakthroughSnapshotResponse(BaseModel):
    contract_version: Literal[1] = 1
    session_id: UUID
    status: str
    source_level: int
    target_level: int
    pill_count: int
    success_basis_points: int
    primary_roll: int
    secondary_roll: int | None
    outcome: Literal["success", "failure_advance", "failure_loss"]
    started_at: datetime
    completes_at: datetime
    settled_at: datetime | None


class ItemAdjustmentRequest(BaseModel):
    item_code: Literal["foundation_pill"]
    delta_quantity: int = Field(gt=0, le=1_000_000)


class ItemAdjustmentResponse(BaseModel):
    contract_version: Literal[1] = 1
    item_code: str
    delta_quantity: int
    balance_after: int
