from uuid import UUID

from immortal_mmo.player.mappers import to_spirit_root_schema
from immortal_mmo.player.models import BASE_ELEMENT_ORDER, SpiritRootGenerator


def test_spirit_root_generator_emits_canonical_codes_in_stable_order() -> None:
    generator = SpiritRootGenerator(
        roll=lambda: 0.10,
        choose_base_elements=lambda count: ("fire", "metal", "water", "wood")[:count],
        choose_variant_pair=lambda: ("metal", "thunder"),
    )

    root = generator.generate(UUID(int=1))

    assert root.quality_code == "quad"
    assert root.base_element_codes == ("metal", "wood", "water", "fire")
    assert root.variant_element_code is None
    assert root.generator_version == 1
    assert BASE_ELEMENT_ORDER == ("metal", "wood", "water", "fire", "earth")


def test_variant_generation_persists_codes_and_maps_chinese_only_for_presentation() -> None:
    root = SpiritRootGenerator(
        roll=lambda: 0.95,
        choose_base_elements=lambda count: BASE_ELEMENT_ORDER[:count],
        choose_variant_pair=lambda: ("metal", "thunder"),
    ).generate(UUID(int=2))

    assert root.base_element_codes == ("metal",)
    assert root.variant_element_code == "thunder"
    assert not hasattr(root, "mutated_element")

    presented = to_spirit_root_schema(root)
    assert presented.model_dump() == {
        "quality": "variant",
        "label": "异灵根",
        "elements": ["金"],
        "mutated_element": "金雷",
        "variant_element": "雷",
    }


def test_generator_covers_all_non_variant_quality_shapes() -> None:
    cases = [
        (0.10, "quad", 4),
        (0.40, "penta", 5),
        (0.70, "triple", 3),
        (0.85, "dual", 2),
        (0.99, "celestial", 1),
    ]
    for roll, quality, count in cases:
        root = SpiritRootGenerator(
            roll=lambda value=roll: value,
            choose_base_elements=lambda size: BASE_ELEMENT_ORDER[:size],
            choose_variant_pair=lambda: ("metal", "thunder"),
        ).generate(UUID(int=count))
        assert root.quality_code == quality
        assert len(root.base_element_codes) == count
