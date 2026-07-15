from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from immortal_mmo.combat.schemas import (
    CombatKillBatchRequest,
    CombatKillBatchResponse,
    CombatKillEventRequest,
    CombatKillResult,
)

EVENT_ID = UUID("11111111-1111-5111-8111-111111111111")
ENTITY_ID = UUID("22222222-2222-4222-8222-222222222222")
KILLER_ID = UUID("33333333-3333-4333-8333-333333333333")
LIFE_ID = UUID("44444444-4444-4444-8444-444444444444")
CAST_ID = UUID("55555555-5555-4555-8555-555555555555")


def event_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": 1,
        "event_id": str(EVENT_ID),
        "server_id": "main-1",
        "entity_uuid": str(ENTITY_ID),
        "mob_internal_name": "AzureWolf",
        "mob_level": "12.500",
        "killer_uuid": str(KILLER_ID),
        "source_life_id": str(LIFE_ID),
        "attribution_kind": "damage_over_time",
        "technique_id": "venom_mist",
        "cast_id": str(CAST_ID),
        "world": "minecraft:overworld",
        "x": 12.5,
        "y": 64.0,
        "z": -8.25,
        "occurred_at": "2026-07-15T12:00:00Z",
    }
    payload.update(overrides)
    return payload


def test_event_request_preserves_decimal_and_attribution_contract() -> None:
    event = CombatKillEventRequest.model_validate(event_payload())

    assert str(event.mob_level) == "12.500"
    assert event.source_life_id == LIFE_ID
    assert event.attribution_kind == "damage_over_time"
    assert event.technique_id == "venom_mist"
    assert event.cast_id == CAST_ID
    assert event.occurred_at == datetime(2026, 7, 15, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mob_level", 12.5),
        ("mob_level", "NaN"),
        ("mob_level", "12.5001"),
        ("mob_internal_name", "contains spaces"),
        ("attribution_kind", "unknown"),
        ("occurred_at", "2026-07-15T12:00:00"),
    ],
)
def test_event_request_rejects_invalid_wire_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        CombatKillEventRequest.model_validate(event_payload(**{field: value}))


def test_batch_rejects_duplicate_event_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate event_id"):
        CombatKillBatchRequest.model_validate(
            {
                "contract_version": 1,
                "events": [event_payload(), event_payload()],
            }
        )


def test_batch_rejects_more_than_two_hundred_events() -> None:
    events = [
        event_payload(event_id=str(UUID(int=index + 1)))
        for index in range(201)
    ]

    with pytest.raises(ValidationError):
        CombatKillBatchRequest.model_validate(
            {"contract_version": 1, "events": events}
        )


def test_batch_response_carries_terminal_per_event_results() -> None:
    response = CombatKillBatchResponse(
        results=[
            CombatKillResult(
                event_id=EVENT_ID,
                outcome="accepted",
                kill_event_id=ENTITY_ID,
                life_id=LIFE_ID,
                reward_amount=120,
                unrefined_balance=4800,
            )
        ]
    )

    assert response.contract_version == 1
    assert response.results[0].outcome == "accepted"
    assert response.results[0].reward_amount == 120
