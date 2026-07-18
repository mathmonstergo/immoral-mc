from collections.abc import Mapping
from types import MappingProxyType

CULTIVATION_CYCLE_SECONDS = 10
MAJOR_REALM_SPEED_WEIGHTS: Mapping[str, int] = MappingProxyType(
    {"练气": 1, "筑基": 2, "结丹": 5, "元婴": 10}
)
FULL_MASTERY_SECONDS: Mapping[str, int] = MappingProxyType(
    {"练气": 36_000, "筑基": 72_000, "结丹": 180_000, "元婴": 360_000}
)


def speed_weight_for_major_realm(major_realm: str) -> int:
    try:
        return MAJOR_REALM_SPEED_WEIGHTS[major_realm]
    except KeyError as error:
        raise ValueError(f"Unsupported major realm: {major_realm}") from error


def full_mastery_seconds_for_major_realm(major_realm: str) -> int:
    try:
        return FULL_MASTERY_SECONDS[major_realm]
    except KeyError as error:
        raise ValueError(f"Unsupported major realm: {major_realm}") from error


def base_cycle_rate(
    *,
    technique_capacity: int,
    full_mastery_seconds: int,
    cycle_seconds: int = CULTIVATION_CYCLE_SECONDS,
) -> int:
    _positive_int(technique_capacity, "technique_capacity")
    _positive_int(full_mastery_seconds, "full_mastery_seconds")
    _positive_int(cycle_seconds, "cycle_seconds")
    return max(technique_capacity * cycle_seconds // full_mastery_seconds, 1)


def scaled_cycle_rate(
    *,
    base_rate: int,
    player_speed_weight: int,
    technique_speed_weight: int,
    area_speed_basis_points: int,
) -> int:
    _positive_int(base_rate, "base_rate")
    _positive_int(player_speed_weight, "player_speed_weight")
    _positive_int(technique_speed_weight, "technique_speed_weight")
    _positive_int(area_speed_basis_points, "area_speed_basis_points")
    return max(
        base_rate
        * player_speed_weight
        * area_speed_basis_points
        // (technique_speed_weight * 10_000),
        1,
    )


def cumulative_cycle_budget(
    *,
    elapsed_seconds: int,
    cultivation_per_cycle: int,
    cycle_seconds: int = CULTIVATION_CYCLE_SECONDS,
) -> int:
    _non_negative_int(elapsed_seconds, "elapsed_seconds")
    _positive_int(cultivation_per_cycle, "cultivation_per_cycle")
    _positive_int(cycle_seconds, "cycle_seconds")
    return elapsed_seconds // cycle_seconds * cultivation_per_cycle


def reserve_required_for_retained(
    retained_cap: int,
    yield_basis_points: int,
) -> int:
    _non_negative_int(retained_cap, "retained_cap")
    _positive_int(yield_basis_points, "yield_basis_points")
    return (retained_cap * 10_000 + yield_basis_points - 1) // yield_basis_points


def _positive_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")


def _non_negative_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
