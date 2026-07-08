from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

LifeStatus = Literal["alive", "reincarnated"]
SpiritRootQuality = Literal["quad", "penta", "triple", "dual", "variant", "celestial"]


class SpiritRoot(BaseModel):
    quality: SpiritRootQuality
    label: str
    elements: list[str] = Field(min_length=1)
    mutated_element: str | None = None
    variant_element: str | None = None


class Account(BaseModel):
    account_id: UUID
    minecraft_uuid: UUID
    player_name: str


class Life(BaseModel):
    life_id: UUID
    account_id: UUID
    generation_no: int
    status: LifeStatus
    spirit_root: SpiritRoot | None


class PlayerLoginRequest(BaseModel):
    minecraft_uuid: UUID
    player_name: str


class PlayerLoginResponse(BaseModel):
    account: Account
    current_life: Life


class SpiritRootDetectionResponse(BaseModel):
    life_id: UUID
    spirit_root: SpiritRoot
    already_detected: bool

