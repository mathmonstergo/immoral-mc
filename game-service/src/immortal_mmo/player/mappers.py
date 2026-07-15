from typing import cast

from immortal_mmo.player.db_models import AccountRow, LifeRow, LifeSpiritRootRow
from immortal_mmo.player.models import (
    Account,
    Life,
    LifeStatus,
    SpiritRoot,
    SpiritRootQuality,
)
from immortal_mmo.player.schemas import (
    AccountSchema,
    LifeSchema,
    PlayerLoginResponse,
    SpiritRootSchema,
)

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


def account_from_row(row: AccountRow) -> Account:
    return Account(
        account_id=row.account_id,
        minecraft_uuid=row.minecraft_uuid,
        last_known_name=row.last_known_name,
        revision=row.revision,
    )


def life_from_row(row: LifeRow) -> Life:
    return Life(
        life_id=row.life_id,
        account_id=row.account_id,
        generation_no=row.generation_no,
        status=cast(LifeStatus, row.status),
        revision=row.revision,
    )


def spirit_root_from_row(row: LifeSpiritRootRow) -> SpiritRoot:
    return SpiritRoot(
        life_id=row.life_id,
        quality_code=cast(SpiritRootQuality, row.quality_code),
        base_element_codes=tuple(row.base_element_codes),
        variant_element_code=row.variant_element_code,
        generator_version=row.generator_version,
    )


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
