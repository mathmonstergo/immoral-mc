import pytest

from immortal_mmo.cultivation.seclusion import (
    cumulative_time_budget,
    incremental_time_budget,
    maximum_convertible_reserve,
)


def test_partial_settlements_equal_one_combined_settlement() -> None:
    one = cumulative_time_budget(7200, 10_000, [3_765], 36_000)
    split = cumulative_time_budget(3600, 10_000, [3_765], 36_000)
    assert one - split == incremental_time_budget(
        elapsed_seconds=7200,
        prior_cumulative=split,
        speed_basis_points=10_000,
        capacities=[3_765],
        full_mastery_seconds=36_000,
    )


def test_inverse_yield_never_exceeds_effective_cap() -> None:
    consumed = maximum_convertible_reserve(100, 15_000)
    assert consumed == 67
    assert consumed * 15_000 // 10_000 <= 100


@pytest.mark.parametrize("value", [0, -1, True])
def test_time_budget_rejects_invalid_elapsed(value: object) -> None:
    with pytest.raises(ValueError):
        cumulative_time_budget(value, 10_000, [100], 3_600)  # type: ignore[arg-type]


def test_multi_selection_uses_average_capacity_rate() -> None:
    assert cumulative_time_budget(3_600, 10_000, [100, 300], 36_000) == 20
