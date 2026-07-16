import hashlib
import hmac
from collections.abc import Mapping
from uuid import UUID

PENALTY_ENTROPY_BYTES = 32


def breakthrough_penalty(max_exp: int) -> int:
    if isinstance(max_exp, bool) or not isinstance(max_exp, int) or max_exp <= 0:
        raise ValueError("Breakthrough max_exp must be a positive integer")
    return max_exp // 3


def allocate_breakthrough_penalty(
    *,
    total: int,
    investments: Mapping[UUID, int],
    entropy: bytes,
) -> dict[UUID, int]:
    if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
        raise ValueError("Breakthrough penalty total must be positive")
    if len(entropy) != PENALTY_ENTROPY_BYTES:
        raise ValueError("Breakthrough penalty entropy must be exactly 32 bytes")
    if not investments:
        raise ValueError("Breakthrough penalty requires invested techniques")
    if any(
        isinstance(amount, bool) or not isinstance(amount, int) or amount < 0
        for amount in investments.values()
    ):
        raise ValueError("Technique investments must be non-negative integers")
    if total > sum(investments.values()):
        raise ValueError("Breakthrough penalty exceeds available investment")

    debits = {technique_id: 0 for technique_id in investments}
    available = {
        technique_id: amount
        for technique_id, amount in investments.items()
        if amount > 0
    }
    remaining = total
    round_index = 0
    while remaining > 0:
        weighted = {
            technique_id: _round_weight(entropy, round_index, technique_id)
            for technique_id in available
        }
        weight_total = sum(weight for weight, _ in weighted.values())
        proposed = {
            technique_id: remaining * weight // weight_total
            for technique_id, (weight, _) in weighted.items()
        }
        points_left = remaining - sum(proposed.values())
        remainder_order = sorted(
            weighted,
            key=lambda technique_id: (
                -(remaining * weighted[technique_id][0] % weight_total),
                weighted[technique_id][1],
                technique_id.bytes,
            ),
        )
        for technique_id in remainder_order[:points_left]:
            proposed[technique_id] += 1

        applied = 0
        for technique_id in tuple(sorted(available, key=lambda value: value.bytes)):
            debit = min(proposed[technique_id], available[technique_id])
            debits[technique_id] += debit
            available[technique_id] -= debit
            applied += debit
            if available[technique_id] == 0:
                del available[technique_id]
        if applied <= 0:
            raise RuntimeError("Breakthrough penalty allocator made no progress")
        remaining -= applied
        round_index += 1

    return debits


def _round_weight(entropy: bytes, round_index: int, technique_id: UUID) -> tuple[int, bytes]:
    message = round_index.to_bytes(8, "big", signed=False) + technique_id.bytes
    digest = hmac.new(entropy, message, hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big", signed=False) + 1, digest
