from typing import Literal

from pydantic import BaseModel


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
