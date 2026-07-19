from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from immortal_mmo.item.schemas import ItemInstanceProjection


class StorageSlotProjection(BaseModel):
    slot: int
    item: ItemInstanceProjection


class StorageSnapshotResponse(BaseModel):
    contract_version: Literal[1] = 1
    life_id: UUID
    area_id: str
    catalog_revision: str
    permission: str
    page: int
    page_count: int
    item_slots_per_page: int
    revision: int
    slots: list[StorageSlotProjection]


class StorageMoveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    move_kind: Literal["deposit", "withdraw", "move"]
    item_instance_id: UUID
    expected_revision: int = Field(ge=0)
    source_page: int | None = Field(default=None, ge=1)
    source_slot: int | None = Field(default=None, ge=0, le=44)
    destination_page: int | None = Field(default=None, ge=1)
    destination_slot: int | None = Field(default=None, ge=0, le=44)
    view_page: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_shape(self) -> "StorageMoveRequest":
        source_present = self.source_page is not None and self.source_slot is not None
        destination_present = (
            self.destination_page is not None and self.destination_slot is not None
        )
        if (self.source_page is None) != (self.source_slot is None):
            raise ValueError("source_page and source_slot must be supplied together")
        if (self.destination_page is None) != (self.destination_slot is None):
            raise ValueError(
                "destination_page and destination_slot must be supplied together"
            )
        if self.move_kind == "deposit" and (source_present or not destination_present):
            raise ValueError("deposit requires only a destination storage slot")
        if self.move_kind == "withdraw" and (not source_present or destination_present):
            raise ValueError("withdraw requires only a source storage slot")
        if self.move_kind == "move":
            if not source_present or not destination_present:
                raise ValueError("move requires source and destination storage slots")
            if (self.source_page, self.source_slot) == (
                self.destination_page,
                self.destination_slot,
            ):
                raise ValueError("move source and destination must differ")
        return self


class StorageMoveResponse(BaseModel):
    contract_version: Literal[1] = 1
    operation_id: UUID
    move_kind: Literal["deposit", "withdraw", "move"]
    item_instance_id: UUID
    snapshot: StorageSnapshotResponse
