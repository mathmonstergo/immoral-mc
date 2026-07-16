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
