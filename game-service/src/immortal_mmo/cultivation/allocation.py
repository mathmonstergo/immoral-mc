from collections.abc import Iterable, Mapping
from uuid import UUID


def allocate_equal(
    amount: int,
    remaining_by_uuid: Mapping[UUID, int] | Iterable[tuple[UUID, int]],
) -> dict[UUID, int]:
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise ValueError("amount must be a non-negative integer")

    source = (
        remaining_by_uuid.items() if isinstance(remaining_by_uuid, Mapping) else remaining_by_uuid
    )
    pairs = list(source)
    capacities: dict[UUID, int] = {}
    for technique_uuid, capacity in pairs:
        if technique_uuid in capacities:
            raise ValueError(f"Duplicate technique UUID: {technique_uuid}")
        if not isinstance(technique_uuid, UUID):
            raise ValueError("Technique IDs must be UUID values")
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
            raise ValueError("Technique remaining capacity must be a non-negative integer")
        capacities[technique_uuid] = capacity

    ordered_ids = sorted(capacities)
    allocations = {technique_uuid: 0 for technique_uuid in ordered_ids}
    active = [technique_uuid for technique_uuid in ordered_ids if capacities[technique_uuid] > 0]
    total_to_allocate = min(amount, sum(capacities.values()))
    if not total_to_allocate or not active:
        return allocations

    low, high = 0, max(capacities.values())
    while low < high:
        candidate = (low + high + 1) // 2
        used = sum(min(capacities[technique_uuid], candidate) for technique_uuid in active)
        if used <= total_to_allocate:
            low = candidate
        else:
            high = candidate - 1

    for technique_uuid in active:
        allocations[technique_uuid] = min(capacities[technique_uuid], low)

    remainder = total_to_allocate - sum(allocations.values())
    for technique_uuid in active:
        if not remainder:
            break
        if allocations[technique_uuid] < capacities[technique_uuid]:
            allocations[technique_uuid] += 1
            remainder -= 1

    return allocations
