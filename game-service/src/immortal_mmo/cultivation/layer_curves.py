TRANSITION_COUNT = 12


def build_transition_costs(capacity: int, p: int, q: int) -> tuple[int, ...]:
    for value, label in ((capacity, "capacity"), (p, "p"), (q, "q")):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive integer")
    if capacity < TRANSITION_COUNT:
        raise ValueError("capacity must allow twelve positive transition costs")

    weights = tuple(p**index * q ** (TRANSITION_COUNT - 1 - index) for index in range(12))
    total_weight = sum(weights)
    costs = [capacity * weight // total_weight for weight in weights]
    points_left = capacity - sum(costs)
    remainder_order = sorted(
        range(TRANSITION_COUNT),
        key=lambda index: (-(capacity * weights[index] % total_weight), index),
    )
    for index in remainder_order[:points_left]:
        costs[index] += 1
    if any(cost == 0 for cost in costs):
        raise ValueError("capacity and ratio must produce positive transition costs")

    return tuple(costs)
