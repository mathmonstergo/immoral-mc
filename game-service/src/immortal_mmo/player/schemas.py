from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SpiritRootSchema(BaseModel):
    quality: Literal["quad", "penta", "triple", "dual", "variant", "celestial"]
    label: str
    elements: list[str] = Field(min_length=1)
    mutated_element: str | None = None
    variant_element: str | None = None


class AccountSchema(BaseModel):
    account_id: UUID
    minecraft_uuid: UUID
    player_name: str


class LifeSchema(BaseModel):
    life_id: UUID
    account_id: UUID
    generation_no: int
    status: Literal["alive", "reincarnated"]
    spirit_root: SpiritRootSchema | None


class PlayerLoginRequest(BaseModel):
    minecraft_uuid: UUID
    player_name: str = Field(pattern=r"^[A-Za-z0-9_]{3,16}$")


class PlayerLoginResponse(BaseModel):
    account: AccountSchema
    current_life: LifeSchema


class SpiritRootDetectionResponse(BaseModel):
    life_id: UUID
    spirit_root: SpiritRootSchema
    already_detected: bool
