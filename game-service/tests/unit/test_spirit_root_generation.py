from immortal_mmo.player.service import BASE_ELEMENTS, SpiritRootGenerator


def test_spirit_root_quality_buckets_are_rolled_before_elements() -> None:
    element_calls: list[int] = []

    def choose_base_elements(count: int) -> list[str]:
        element_calls.append(count)
        return BASE_ELEMENTS[:count]

    generator = SpiritRootGenerator(
        roll=lambda: 0.10,
        choose_base_elements=choose_base_elements,
        choose_mutated_element=lambda: "金雷",
    )

    root = generator.generate()

    assert root.quality == "quad"
    assert root.label == "伪灵根"
    assert root.elements == ["金", "木", "水", "火"]
    assert root.mutated_element is None
    assert root.variant_element is None
    assert element_calls == [4]


def test_spirit_root_generator_covers_all_quality_buckets() -> None:
    cases = [
        (0.10, "quad", "伪灵根", ["金", "木", "水", "火"]),
        (0.40, "penta", "伪灵根", ["金", "木", "水", "火", "土"]),
        (0.70, "triple", "三灵根", ["金", "木", "水"]),
        (0.85, "dual", "双灵根", ["金", "木"]),
        (0.99, "celestial", "天灵根", ["金"]),
    ]

    for roll, quality, label, elements in cases:
        generator = SpiritRootGenerator(
            roll=lambda value=roll: value,
            choose_base_elements=lambda count: BASE_ELEMENTS[:count],
            choose_mutated_element=lambda: "金雷",
        )

        root = generator.generate()

        assert root.quality == quality
        assert root.label == label
        assert root.elements == elements
        assert root.mutated_element is None
        assert root.variant_element is None


def test_variant_spirit_root_splits_base_and_variant_attributes() -> None:
    generator = SpiritRootGenerator(
        roll=lambda: 0.95,
        choose_base_elements=lambda count: BASE_ELEMENTS[:count],
        choose_mutated_element=lambda: "金雷",
    )

    root = generator.generate()

    assert root.quality == "variant"
    assert root.label == "异灵根"
    assert root.elements == ["金"]
    assert root.mutated_element == "金雷"
    assert root.variant_element == "雷"

