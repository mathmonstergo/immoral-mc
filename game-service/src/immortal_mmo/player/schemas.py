from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from immortal_mmo.player.models import Account, Life, SpiritRoot

ELEMENT_LABELS = {
    "metal": "金",
    "wood": "木",
    "water": "水",
    "fire": "火",
    "earth": "土",
}
VARIANT_LABELS = {"wind": "风", "thunder": "雷", "ice": "冰", "dark": "暗"}
QUALITY_LABELS = {
    "quad": "伪灵根",
    "penta": "伪灵根",
    "triple": "三灵根",
    "dual": "双灵根",
    "variant": "异灵根",
    "celestial": "天灵根",
}


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
    player_name: str


class PlayerLoginResponse(BaseModel):
    account: AccountSchema
    current_life: LifeSchema


class SpiritRootDetectionResponse(BaseModel):
    life_id: UUID
    spirit_root: SpiritRootSchema
    already_detected: bool


def to_spirit_root_schema(root: SpiritRoot) -> SpiritRootSchema:
    elements = [ELEMENT_LABELS[element] for element in root.base_element_codes]
    variant = VARIANT_LABELS[root.variant_element_code] if root.variant_element_code else None
    mutated = f"{elements[0]}{variant}" if variant else None
    return SpiritRootSchema(
        quality=root.quality_code,
        label=QUALITY_LABELS[root.quality_code],
        elements=elements,
        mutated_element=mutated,
        variant_element=variant,
    )


def to_login_response(
    account: Account,
    life: Life,
    spirit_root: SpiritRoot | None,
) -> PlayerLoginResponse:
    return PlayerLoginResponse(
        account=AccountSchema(
            account_id=account.account_id,
            minecraft_uuid=account.minecraft_uuid,
            player_name=account.last_known_name,
        ),
        current_life=LifeSchema(
            life_id=life.life_id,
            account_id=life.account_id,
            generation_no=life.generation_no,
            status=life.status,
            spirit_root=to_spirit_root_schema(spirit_root) if spirit_root else None,
        ),
    )
