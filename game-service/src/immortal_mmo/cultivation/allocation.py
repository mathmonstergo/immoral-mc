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
    amount_left = min(amount, sum(capacities.values()))

    while amount_left and active:
        share, remainder = divmod(amount_left, len(active))
        distributed = 0
        next_active: list[UUID] = []
        for index, technique_uuid in enumerate(active):
            requested = share + (1 if index < remainder else 0)
            available = capacities[technique_uuid] - allocations[technique_uuid]
            granted = min(requested, available)
            allocations[technique_uuid] += granted
            distributed += granted
            if allocations[technique_uuid] < capacities[technique_uuid]:
                next_active.append(technique_uuid)
        amount_left -= distributed
        active = next_active

    return allocations
