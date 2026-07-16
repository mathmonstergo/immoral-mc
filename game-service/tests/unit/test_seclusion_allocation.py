from uuid import UUID

import pytest

from immortal_mmo.cultivation.allocation import allocate_equal


def uid(value: int) -> UUID:
    return UUID(int=value)


@pytest.mark.parametrize(
    ("count", "amount", "expected"),
    [
        (1, 5, {uid(1): 5}),
        (3, 8, {uid(1): 3, uid(2): 3, uid(3): 2}),
        (5, 12, {uid(1): 3, uid(2): 3, uid(3): 2, uid(4): 2, uid(5): 2}),
        (
            9,
            13,
            {
                uid(1): 2,
                uid(2): 2,
                uid(3): 2,
                uid(4): 2,
                uid(5): 1,
                uid(6): 1,
                uid(7): 1,
                uid(8): 1,
                uid(9): 1,
            },
        ),
    ],
)
def test_equal_allocation_for_one_three_five_and_nine_techniques(
    count: int,
    amount: int,
    expected: dict[UUID, int],
) -> None:
    capacities = {uid(index): 100 for index in range(count, 0, -1)}

    assert allocate_equal(amount, capacities) == expected


def test_equal_allocation_redistributes_full_technique_overflow() -> None:
    result = allocate_equal(
        amount=11,
        remaining_by_uuid={uid(1): 2, uid(2): 100, uid(3): 100},
    )

    assert result == {uid(1): 2, uid(2): 5, uid(3): 4}


def test_equal_allocation_handles_mid_settlement_mastery_repeatedly() -> None:
    result = allocate_equal(
        amount=20,
        remaining_by_uuid={uid(1): 1, uid(2): 4, uid(3): 100, uid(4): 100},
    )

    assert result == {uid(1): 1, uid(2): 4, uid(3): 8, uid(4): 7}


def test_equal_allocation_is_order_independent() -> None:
    ascending = {uid(1): 2, uid(2): 100, uid(3): 100}
    descending = {uid(3): 100, uid(2): 100, uid(1): 2}

    assert allocate_equal(11, ascending) == allocate_equal(11, descending)


def test_equal_allocation_ignores_full_techniques_and_caps_total() -> None:
    assert allocate_equal(99, {uid(1): 0, uid(2): 2, uid(3): 3}) == {
        uid(1): 0,
        uid(2): 2,
        uid(3): 3,
    }
    assert allocate_equal(0, {uid(1): 10}) == {uid(1): 0}


@pytest.mark.parametrize(
    ("amount", "remaining"),
    [
        (-1, {uid(1): 1}),
        (1, {uid(1): -1}),
        (True, {uid(1): 1}),
        (1, {uid(1): True}),
    ],
)
def test_equal_allocation_rejects_negative_and_non_integer_inputs(
    amount: int,
    remaining: dict[UUID, int],
) -> None:
    with pytest.raises(ValueError):
        allocate_equal(amount, remaining)


def test_equal_allocation_rejects_duplicate_uuid_pairs() -> None:
    with pytest.raises(ValueError, match="Duplicate technique UUID"):
        allocate_equal(1, [(uid(1), 1), (uid(1), 2)])
