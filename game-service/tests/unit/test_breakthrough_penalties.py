from uuid import UUID

import pytest

from immortal_mmo.cultivation.penalties import (
    allocate_breakthrough_penalty,
    breakthrough_penalty,
)


@pytest.mark.parametrize(
    ("max_exp", "expected"),
    [(3_829, 1_276), (5_169, 1_723), (6_978, 2_326), (9_420, 3_140)],
)
def test_penalty_total_uses_floor(max_exp: int, expected: int) -> None:
    assert breakthrough_penalty(max_exp) == expected


def test_hmac_allocator_has_stable_capacity_aware_multi_round_golden_vector() -> None:
    technique_ids = tuple(UUID(int=value) for value in range(1, 5))
    balances = {
        technique_ids[0]: 500,
        technique_ids[1]: 500,
        technique_ids[2]: 500,
        technique_ids[3]: 100,
    }

    result = allocate_breakthrough_penalty(
        total=600,
        investments=balances,
        entropy=bytes(range(32)),
    )

    assert result == {
        technique_ids[0]: 64,
        technique_ids[1]: 278,
        technique_ids[2]: 158,
        technique_ids[3]: 100,
    }
    assert sum(result.values()) == 600
    assert all(result[key] <= balances[key] for key in balances)


def test_hmac_allocator_is_input_order_invariant() -> None:
    technique_ids = tuple(UUID(int=value) for value in range(1, 5))
    balances = {technique_id: 1_000 for technique_id in technique_ids}
    reverse = dict(reversed(tuple(balances.items())))

    first = allocate_breakthrough_penalty(
        total=1_000,
        investments=balances,
        entropy=b"fixed-entropy".ljust(32, b"\0"),
    )
    second = allocate_breakthrough_penalty(
        total=1_000,
        investments=reverse,
        entropy=b"fixed-entropy".ljust(32, b"\0"),
    )

    assert first == second


@pytest.mark.parametrize(
    ("total", "investments", "entropy", "message"),
    [
        (0, {UUID(int=1): 1}, bytes(32), "positive"),
        (2, {UUID(int=1): 1}, bytes(32), "exceeds"),
        (1, {UUID(int=1): -1}, bytes(32), "non-negative"),
        (1, {UUID(int=1): 1}, b"short", "32 bytes"),
    ],
)
def test_hmac_allocator_rejects_invalid_inputs(
    total: int,
    investments: dict[UUID, int],
    entropy: bytes,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        allocate_breakthrough_penalty(
            total=total,
            investments=investments,
            entropy=entropy,
        )
