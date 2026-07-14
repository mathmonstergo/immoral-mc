from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import SystemRandom
from typing import Literal
from uuid import UUID

LifeStatus = Literal["alive", "reincarnated"]
SpiritRootQuality = Literal["quad", "penta", "triple", "dual", "variant", "celestial"]

BASE_ELEMENT_ORDER = ("metal", "wood", "water", "fire", "earth")
VARIANT_ELEMENT_PAIRS = (
    ("fire", "wind"),
    ("wood", "wind"),
    ("metal", "thunder"),
    ("water", "thunder"),
    ("fire", "thunder"),
    ("water", "ice"),
    ("wood", "ice"),
    ("metal", "dark"),
    ("earth", "dark"),
)


@dataclass(frozen=True, slots=True)
class Account:
    account_id: UUID
    minecraft_uuid: UUID
    last_known_name: str
    revision: int


@dataclass(frozen=True, slots=True)
class Life:
    life_id: UUID
    account_id: UUID
    generation_no: int
    status: LifeStatus
    revision: int


@dataclass(frozen=True, slots=True)
class SpiritRoot:
    life_id: UUID
    quality_code: SpiritRootQuality
    base_element_codes: tuple[str, ...]
    variant_element_code: str | None
    generator_version: int


@dataclass(frozen=True, slots=True)
class CurrentLifeQuestFacts:
    account_id: UUID
    life_id: UUID
    generation_no: int
    spirit_root: SpiritRoot | None
    revision: int


class SpiritRootGenerator:
    def __init__(
        self,
        roll: Callable[[], float] | None = None,
        choose_base_elements: Callable[[int], Sequence[str]] | None = None,
        choose_variant_pair: Callable[[], tuple[str, str]] | None = None,
    ) -> None:
        random = SystemRandom()
        self._roll = roll or random.random
        self._choose_base_elements = choose_base_elements or (
            lambda count: random.sample(BASE_ELEMENT_ORDER, count)
        )
        self._choose_variant_pair = choose_variant_pair or (
            lambda: random.choice(VARIANT_ELEMENT_PAIRS)
        )

    def generate(self, life_id: UUID) -> SpiritRoot:
        quality = self._roll_quality()
        if quality == "variant":
            base, variant = self._choose_variant_pair()
            if (base, variant) not in VARIANT_ELEMENT_PAIRS:
                raise ValueError("Unsupported spirit-root variant pair")
            return SpiritRoot(life_id, quality, (base,), variant, 1)
        count = {"quad": 4, "penta": 5, "triple": 3, "dual": 2, "celestial": 1}[
            quality
        ]
        selected = set(self._choose_base_elements(count))
        if len(selected) != count or not selected.issubset(BASE_ELEMENT_ORDER):
            raise ValueError("Invalid base spirit-root elements")
        canonical = tuple(element for element in BASE_ELEMENT_ORDER if element in selected)
        return SpiritRoot(life_id, quality, canonical, None, 1)

    def _roll_quality(self) -> SpiritRootQuality:
        value = self._roll()
        if value < 0.30:
            return "quad"
        if value < 0.60:
            return "penta"
        if value < 0.80:
            return "triple"
        if value < 0.92:
            return "dual"
        if value < 0.97:
            return "variant"
        return "celestial"
