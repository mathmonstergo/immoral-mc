import pytest

from immortal_mmo.cultivation.layer_curves import build_transition_costs


@pytest.mark.parametrize("capacity,ratio", [(3_765, (3, 2)), (14_644, (17, 10))])
def test_layer_costs_are_positive_exact_and_reproducible(
    capacity: int,
    ratio: tuple[int, int],
) -> None:
    first = build_transition_costs(capacity, *ratio)
    second = build_transition_costs(capacity, *ratio)

    assert first == second
    assert len(first) == 12
    assert all(cost > 0 for cost in first)
    assert sum(first) == capacity


@pytest.mark.parametrize("ratio", [(3, 2), (17, 10), (9, 5), (2, 1)])
def test_layer_costs_follow_the_approved_monotonic_growth_shape(
    ratio: tuple[int, int],
) -> None:
    costs = build_transition_costs(100_000, *ratio)

    assert all(left < right for left, right in zip(costs[:-1], costs[1:], strict=True))


def test_largest_fractional_remainder_tie_prefers_lower_transition_index() -> None:
    assert build_transition_costs(13, 1, 1) == (2,) + (1,) * 11


def test_largest_remainders_can_make_zero_floor_quotas_positive() -> None:
    assert build_transition_costs(12, 101, 100) == (1,) * 12


@pytest.mark.parametrize(
    ("capacity", "p", "q"),
    [
        (0, 3, 2),
        (-1, 3, 2),
        (11, 1, 1),
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


def test_layer_costs_reject_ratios_that_cannot_make_every_transition_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_transition_costs(12, 2, 1)
