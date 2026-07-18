from functools import lru_cache

BASE_TRANSITION_COUNT = 12
TRANSITION_COUNT = 13
TECHNIQUE_GROWTH_RATIOS = {
    "练气": (3, 2),
    "筑基": (17, 10),
    "结丹": (9, 5),
    "元婴": (2, 1),
}


def expand_mastery_capacity(base_capacity: int, p: int, q: int) -> int:
    _validate_positive_ints(((base_capacity, "base_capacity"), (p, "p"), (q, "q")))
    costs = _build_base_transition_costs(base_capacity, p, q)
    return base_capacity + costs[0]


def build_transition_costs(capacity: int, p: int, q: int) -> tuple[int, ...]:
    for value, label in ((capacity, "capacity"), (p, "p"), (q, "q")):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")
    if capacity < TRANSITION_COUNT:
        raise ValueError("capacity must allow thirteen positive transition costs")
    return _build_transition_costs(capacity, p, q)


@lru_cache(maxsize=256)
def _build_transition_costs(capacity: int, p: int, q: int) -> tuple[int, ...]:
    base_capacity = _find_base_capacity(capacity, p, q)
    base_costs = _build_base_transition_costs(base_capacity, p, q)
    costs = (base_costs[0], *base_costs)
    if sum(costs) != capacity:
        raise RuntimeError("Expanded technique curve does not match mastery capacity")
    return costs


def _find_base_capacity(capacity: int, p: int, q: int) -> int:
    weights = _base_weights(p, q)
    lower = BASE_TRANSITION_COUNT
    upper = capacity
    while lower < upper:
        candidate = (lower + upper) // 2
        expanded = candidate + _allocate_largest_remainder(candidate, weights)[0]
        if expanded < capacity:
            lower = candidate + 1
        else:
            upper = candidate

    base_costs = _allocate_largest_remainder(lower, weights)
    if lower + base_costs[0] != capacity or any(cost == 0 for cost in base_costs):
        raise ValueError(
            "capacity must be produced by expanding a valid twelve-transition curve"
        )
    return lower


def _build_base_transition_costs(capacity: int, p: int, q: int) -> tuple[int, ...]:
    if capacity < BASE_TRANSITION_COUNT:
        raise ValueError("base_capacity must allow twelve positive transition costs")
    costs = _allocate_largest_remainder(capacity, _base_weights(p, q))
    if any(cost == 0 for cost in costs):
        raise ValueError("base capacity and ratio must produce positive transition costs")
    return costs


def _base_weights(p: int, q: int) -> tuple[int, ...]:
    return tuple(
        p**index * q ** (BASE_TRANSITION_COUNT - 1 - index)
        for index in range(BASE_TRANSITION_COUNT)
    )


def _allocate_largest_remainder(
    capacity: int,
    weights: tuple[int, ...],
) -> tuple[int, ...]:
    total_weight = sum(weights)
    costs = [capacity * weight // total_weight for weight in weights]
    points_left = capacity - sum(costs)
    remainder_order = sorted(
        range(len(weights)),
        key=lambda index: (-(capacity * weights[index] % total_weight), index),
    )
    for index in remainder_order[:points_left]:
        costs[index] += 1
    return tuple(costs)


def _validate_positive_ints(values: tuple[tuple[int, str], ...]) -> None:
    for value, label in values:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")


def layer_for_investment(
    invested_amount: int,
    capacity: int,
    p: int,
    q: int,
) -> int:
    if (
        isinstance(invested_amount, bool)
        or not isinstance(invested_amount, int)
        or invested_amount < 0
        or invested_amount > capacity
    ):
        raise ValueError("invested_amount must be within technique capacity")
    cumulative = 0
    layer = 0
    for cost in build_transition_costs(capacity, p, q):
        cumulative += cost
        if invested_amount < cumulative:
            break
        layer += 1
    return min(layer, TRANSITION_COUNT)


def layer_for_major_realm(
    invested_amount: int,
    capacity: int,
    major_realm: str,
) -> int:
    try:
        ratio = TECHNIQUE_GROWTH_RATIOS[major_realm]
    except KeyError as error:
        raise ValueError(f"Unknown technique major realm: {major_realm}") from error
    return layer_for_investment(invested_amount, capacity, *ratio)
