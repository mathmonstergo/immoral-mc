import pytest

from immortal_mmo.cultivation.seclusion import (
    CULTIVATION_CYCLE_SECONDS,
    base_cycle_rate,
    cumulative_cycle_budget,
    reserve_required_for_retained,
    scaled_cycle_rate,
    speed_weight_for_major_realm,
)


def test_base_cycle_rate_comes_from_technique_capacity_and_mastery_time() -> None:
    assert base_cycle_rate(technique_capacity=3_780, full_mastery_seconds=36_000) == 1
    assert base_cycle_rate(technique_capacity=43_931, full_mastery_seconds=72_000) == 6


@pytest.mark.parametrize(
    ("player_realm", "technique_realm", "base_rate", "expected"),
    [
        ("筑基", "筑基", 6, 6),
        ("筑基", "练气", 1, 2),
        ("结丹", "筑基", 6, 15),
        ("元婴", "筑基", 6, 30),
        ("元婴", "结丹", 29, 58),
    ],
)
def test_major_realm_weights_scale_speed_only(
    player_realm: str,
    technique_realm: str,
    base_rate: int,
    expected: int,
) -> None:
    assert scaled_cycle_rate(
        base_rate=base_rate,
        player_speed_weight=speed_weight_for_major_realm(player_realm),
        technique_speed_weight=speed_weight_for_major_realm(technique_realm),
        area_speed_basis_points=10_000,
    ) == expected


def test_area_speed_scales_the_cycle_rate() -> None:
    assert scaled_cycle_rate(
        base_rate=6,
        player_speed_weight=2,
        technique_speed_weight=2,
        area_speed_basis_points=15_000,
    ) == 9


@pytest.mark.parametrize(
    ("elapsed_seconds", "expected"),
    [(0, 0), (9, 0), (10, 7), (25, 14)],
)
def test_cycle_budget_uses_complete_ten_second_cycles(
    elapsed_seconds: int,
    expected: int,
) -> None:
    assert cumulative_cycle_budget(
        elapsed_seconds=elapsed_seconds,
        cultivation_per_cycle=7,
    ) == expected


def test_partial_settlements_equal_one_combined_settlement() -> None:
    first = cumulative_cycle_budget(elapsed_seconds=10, cultivation_per_cycle=7)
    combined = cumulative_cycle_budget(elapsed_seconds=25, cultivation_per_cycle=7)
    assert first + (combined - first) == combined


@pytest.mark.parametrize(
    ("retained_cap", "yield_basis_points", "expected_reserve"),
    [(100, 15_000, 67), (2, 15_000, 2), (1, 5_000, 2), (0, 15_000, 0)],
)
def test_reserve_requirement_can_fill_the_cumulative_retained_cap(
    retained_cap: int,
    yield_basis_points: int,
    expected_reserve: int,
) -> None:
    required = reserve_required_for_retained(retained_cap, yield_basis_points)

    assert required == expected_reserve
    assert min(required * yield_basis_points // 10_000, retained_cap) == retained_cap


@pytest.mark.parametrize("value", [-1, True])
def test_cycle_budget_rejects_invalid_elapsed(value: object) -> None:
    with pytest.raises(ValueError):
        cumulative_cycle_budget(
            elapsed_seconds=value,  # type: ignore[arg-type]
            cultivation_per_cycle=1,
        )


def test_cycle_duration_is_ten_seconds() -> None:
    assert CULTIVATION_CYCLE_SECONDS == 10
