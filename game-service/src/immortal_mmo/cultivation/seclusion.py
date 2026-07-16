from collections.abc import Sequence


def cumulative_time_budget(
    elapsed_seconds: int,
    speed_basis_points: int,
    capacities: Sequence[int],
    full_mastery_seconds: int,
) -> int:
    _positive_int(elapsed_seconds, "elapsed_seconds")
    _positive_int(speed_basis_points, "speed_basis_points")
    _positive_int(full_mastery_seconds, "full_mastery_seconds")
    if not capacities:
        raise ValueError("capacities must not be empty")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in capacities
    ):
        raise ValueError("capacities must contain positive integers")
    return (
        elapsed_seconds
        * speed_basis_points
        * sum(capacities)
        // (full_mastery_seconds * len(capacities) * 10_000)
    )


def incremental_time_budget(
    *,
    elapsed_seconds: int,
    prior_cumulative: int,
    speed_basis_points: int,
    capacities: Sequence[int],
    full_mastery_seconds: int,
) -> int:
    if (
        isinstance(prior_cumulative, bool)
        or not isinstance(prior_cumulative, int)
        or prior_cumulative < 0
    ):
        raise ValueError("prior_cumulative must be a non-negative integer")
    cumulative = cumulative_time_budget(
        elapsed_seconds,
        speed_basis_points,
        capacities,
        full_mastery_seconds,
    )
    return max(cumulative - prior_cumulative, 0)


def maximum_convertible_reserve(
    effective_cap: int,
    yield_basis_points: int,
) -> int:
    if isinstance(effective_cap, bool) or not isinstance(effective_cap, int) or effective_cap < 0:
        raise ValueError("effective_cap must be a non-negative integer")
    _positive_int(yield_basis_points, "yield_basis_points")
    return (((effective_cap + 1) * 10_000) - 1) // yield_basis_points


def _positive_int(value: int, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
