from collections.abc import Callable
from random import SystemRandom
from uuid import UUID

from immortal_mmo.core.errors import NotFoundError
from immortal_mmo.player.repository import InMemoryPlayerRepository
from immortal_mmo.player.schemas import (
    PlayerLoginResponse,
    SpiritRoot,
    SpiritRootDetectionResponse,
)

BASE_ELEMENTS = ["金", "木", "水", "火", "土"]
MUTATED_ELEMENTS = ["火风", "木风", "金雷", "水雷", "火雷", "水冰", "木冰", "金暗", "土暗"]

QUALITY_LABELS = {
    "quad": "伪灵根",
    "penta": "伪灵根",
    "triple": "三灵根",
    "dual": "双灵根",
    "variant": "异灵根",
    "celestial": "天灵根",
}


class PlayerAccountNotFoundError(NotFoundError):
    code = "player.account_not_found"
    message = "Player account was not found."


class SpiritRootGenerator:
    def __init__(
        self,
        roll: Callable[[], float] | None = None,
        choose_base_elements: Callable[[int], list[str]] | None = None,
        choose_mutated_element: Callable[[], str] | None = None,
    ) -> None:
        system_random = SystemRandom()
        self._roll = roll or system_random.random
        self._choose_base_elements = choose_base_elements or (
            lambda count: system_random.sample(BASE_ELEMENTS, count)
        )
        self._choose_mutated_element = choose_mutated_element or (
            lambda: system_random.choice(MUTATED_ELEMENTS)
        )

    def generate(self) -> SpiritRoot:
        quality = self._roll_quality()
        if quality == "penta":
            return self._build_root(quality=quality, elements=BASE_ELEMENTS.copy())
        if quality == "variant":
            return self._build_variant_root(self._choose_mutated_element())

        element_count = {
            "quad": 4,
            "triple": 3,
            "dual": 2,
            "celestial": 1,
        }[quality]
        return self._build_root(
            quality=quality,
            elements=self._choose_base_elements(element_count),
        )

    def _roll_quality(self) -> str:
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

    def _build_root(self, quality: str, elements: list[str]) -> SpiritRoot:
        return SpiritRoot(
            quality=quality,
            label=QUALITY_LABELS[quality],
            elements=elements,
        )

    def _build_variant_root(self, mutated_element: str) -> SpiritRoot:
        base_element, variant_element = self._split_mutated_element(mutated_element)
        return SpiritRoot(
            quality="variant",
            label=QUALITY_LABELS["variant"],
            elements=[base_element],
            mutated_element=mutated_element,
            variant_element=variant_element,
        )

    def _split_mutated_element(self, mutated_element: str) -> tuple[str, str]:
        for element in BASE_ELEMENTS:
            if mutated_element.startswith(element):
                return element, mutated_element.removeprefix(element)
        raise ValueError(f"Unknown mutated element base: {mutated_element}")


class PlayerService:
    def __init__(
        self,
        repository: InMemoryPlayerRepository | None = None,
        spirit_root_generator: SpiritRootGenerator | None = None,
    ) -> None:
        self._repository = repository or InMemoryPlayerRepository()
        self._spirit_root_generator = spirit_root_generator or SpiritRootGenerator()

    def login(self, minecraft_uuid: UUID, player_name: str) -> PlayerLoginResponse:
        account = self._repository.get_or_create_account(minecraft_uuid, player_name)
        current_life = self._repository.get_or_create_current_life(account.account_id)
        return PlayerLoginResponse(account=account, current_life=current_life)

    def detect_current_life_spirit_root(self, account_id: UUID) -> SpiritRootDetectionResponse:
        account = self._repository.get_account(account_id)
        if account is None:
            raise PlayerAccountNotFoundError()

        current_life = self._repository.get_or_create_current_life(account.account_id)
        if current_life.spirit_root is not None:
            return SpiritRootDetectionResponse(
                life_id=current_life.life_id,
                spirit_root=current_life.spirit_root,
                already_detected=True,
            )

        spirit_root = self._spirit_root_generator.generate()
        updated_life = self._repository.set_current_life_spirit_root(account_id, spirit_root)
        return SpiritRootDetectionResponse(
            life_id=updated_life.life_id,
            spirit_root=spirit_root,
            already_detected=False,
        )
