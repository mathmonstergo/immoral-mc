import pytest

from immortal_mmo.cultivation.layer_curves import (
    build_transition_costs,
    expand_mastery_capacity,
    layer_for_investment,
    layer_for_major_realm,
)


@pytest.mark.parametrize(
    ("base_capacity", "ratio", "expected"),
    [
        (
            3_765,
            (3, 2),
            (15, 15, 22, 33, 49, 74, 111, 166, 250, 375, 562, 843, 1_265),
        ),
        (
            14_644,
            (17, 10),
            (18, 18, 30, 51, 87, 147, 250, 425, 723, 1_230, 2_090, 3_553, 6_040),
        ),
        (
            179_237,
            (9, 5),
            (
                124,
                124,
                223,
                402,
                724,
                1_302,
                2_344,
                4_220,
                7_595,
                13_671,
                24_608,
                44_294,
                79_730,
            ),
        ),
        (
            3_226_260,
            (2, 1),
            (
                788,
                788,
                1_576,
                3_151,
                6_303,
                12_606,
                25_211,
                50_423,
                100_845,
                201_690,
                403_381,
                806_762,
                1_613_524,
            ),
        ),
    ],
)
def test_layer_costs_prepend_the_existing_first_transition_without_rebalancing(
    base_capacity: int,
    ratio: tuple[int, int],
    expected: tuple[int, ...],
) -> None:
    capacity = expand_mastery_capacity(base_capacity, *ratio)
    first = build_transition_costs(capacity, *ratio)
    second = build_transition_costs(capacity, *ratio)

    assert first == second == expected
    assert len(first) == 13
    assert first[0] == first[1]
    assert all(cost > 0 for cost in first)
    assert sum(first) == capacity


@pytest.mark.parametrize("ratio", [(3, 2), (17, 10), (9, 5), (2, 1)])
def test_layer_costs_follow_the_approved_monotonic_growth_shape(
    ratio: tuple[int, int],
) -> None:
    capacity = expand_mastery_capacity(100_000, *ratio)
    costs = build_transition_costs(capacity, *ratio)

    assert costs[0] == costs[1]
    assert all(left < right for left, right in zip(costs[1:-1], costs[2:], strict=True))


def test_largest_fractional_remainder_tie_prefers_lower_transition_index() -> None:
    assert expand_mastery_capacity(12, 1, 1) == 13
    assert build_transition_costs(13, 1, 1) == (1,) * 13


def test_non_expanded_capacity_is_rejected_instead_of_rebalancing_the_curve() -> None:
    with pytest.raises(ValueError, match="expanding"):
        build_transition_costs(14, 1, 1)


def test_layer_is_derived_from_authoritative_total_investment() -> None:
    capacity = expand_mastery_capacity(3_765, 3, 2)
    costs = build_transition_costs(capacity, 3, 2)

    assert layer_for_investment(0, capacity, 3, 2) == 0
    assert layer_for_investment(costs[0] - 1, capacity, 3, 2) == 0
    assert layer_for_investment(costs[0], capacity, 3, 2) == 1
    assert layer_for_investment(sum(costs[:2]) - 1, capacity, 3, 2) == 1
    assert layer_for_investment(sum(costs[:2]), capacity, 3, 2) == 2
    assert layer_for_investment(capacity, capacity, 3, 2) == 13


def test_major_realm_layer_uses_the_shared_curve() -> None:
    capacity = expand_mastery_capacity(3_765, 3, 2)
    assert layer_for_major_realm(0, capacity, "练气") == 0
    assert layer_for_major_realm(capacity, capacity, "练气") == 13

    with pytest.raises(ValueError, match="Unknown technique major realm"):
        layer_for_major_realm(0, capacity, "unknown")


@pytest.mark.parametrize(
    ("capacity", "p", "q"),
    [
        (0, 3, 2),
        (-1, 3, 2),
        (12, 1, 1),
        (100, 0, 2),
        (100, 3, 0),
        (100, -3, 2),
        (100, 3, -2),
        (True, 3, 2),
        (100, True, 2),
    ],
)
def test_layer_costs_reject_invalid_inputs(capacity: int, p: int, q: int) -> None:
    with pytest.raises(ValueError):
        build_transition_costs(capacity, p, q)


def test_capacity_expansion_rejects_ratios_that_cannot_make_every_transition_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        expand_mastery_capacity(12, 2, 1)
