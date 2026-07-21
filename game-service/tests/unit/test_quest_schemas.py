from uuid import UUID

import pytest
from pydantic import ValidationError

from immortal_mmo.quest.schemas import (
    ProximityBark,
    QuestObjectiveProjection,
    QuestProviderRequest,
    QuestRewardPreview,
    QuestTurnInRequest,
)


def test_accept_request_rejects_turn_in_inventory_identity_fields() -> None:
    with pytest.raises(ValidationError):
        QuestProviderRequest.model_validate(
            {
                "provider_id": "old-man",
                "expected_life_id": str(UUID(int=10)),
                "inventory_item_instance_ids": [str(UUID(int=1))],
            }
        )


def test_turn_in_request_requires_explicit_inventory_identity_list() -> None:
    with pytest.raises(ValidationError):
        QuestTurnInRequest.model_validate(
            {"provider_id": "old-man", "expected_life_id": str(UUID(int=10))}
        )


@pytest.mark.parametrize("request_type", [QuestProviderRequest, QuestTurnInRequest])
def test_mutation_requests_require_expected_life_id(request_type: type) -> None:
    values: dict[str, object] = {"provider_id": "old-man"}
    if request_type is QuestTurnInRequest:
        values["inventory_item_instance_ids"] = []
    with pytest.raises(ValidationError):
        request_type.model_validate(values)


def test_turn_in_request_rejects_duplicate_inventory_identities() -> None:
    item_id = UUID(int=1)
    with pytest.raises(ValidationError):
        QuestTurnInRequest(
            provider_id="old-man",
            expected_life_id=UUID(int=10),
            inventory_item_instance_ids=[item_id, item_id],
        )


def test_objective_projection_requires_item_code_only_for_item_delivery() -> None:
    item = QuestObjectiveProjection(
        objective_id="ore",
        objective_type="item_delivery",
        title="玄铁",
        item_code="mystic_iron",
        current=20,
        required=15,
        completed=True,
    )
    assert item.current == 20
    with pytest.raises(ValidationError):
        QuestObjectiveProjection(
            objective_id="ore",
            objective_type="item_delivery",
            title="玄铁",
            item_code=None,
            current=0,
            required=15,
            completed=False,
        )
    with pytest.raises(ValidationError):
        QuestObjectiveProjection(
            objective_id="hunt",
            objective_type="mythicmob_kill_count",
            title="苍狼",
            item_code="mystic_iron",
            current=0,
            required=1,
            completed=False,
        )


def test_reward_preview_uses_strict_discriminated_shape() -> None:
    assert QuestRewardPreview(
        reward_id="ore",
        kind="fixed_item",
        item_code="mystic_iron",
        quantity=2,
        cultivation_amount=None,
    ).quantity == 2
    with pytest.raises(ValidationError):
        QuestRewardPreview(
            reward_id="cultivation",
            kind="unrefined_cultivation",
            item_code=None,
            quantity=1,
            cultivation_amount=50,
        )


@pytest.mark.parametrize(
    "values",
    [
        {"key": "", "speaker": "老村民", "text": "话语", "cooldown_seconds": 60},
        {"key": "rule", "speaker": " ", "text": "话语", "cooldown_seconds": 60},
        {"key": "rule", "speaker": "老村民", "text": " 话语", "cooldown_seconds": 60},
        {"key": "rule", "speaker": "老村民", "text": "话语", "cooldown_seconds": 0},
    ],
)
def test_proximity_bark_rejects_invalid_wire_fields(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ProximityBark.model_validate(values)


def test_proximity_bark_accepts_the_256_character_key_boundary() -> None:
    bark = ProximityBark.model_validate(
        {
            "key": "k" * 256,
            "speaker": "老村民",
            "text": "话语",
            "cooldown_seconds": 60,
        }
    )

    assert len(bark.key) == 256


def test_proximity_bark_rejects_a_key_longer_than_the_wire_limit() -> None:
    with pytest.raises(ValidationError):
        ProximityBark.model_validate(
            {
                "key": "k" * 257,
                "speaker": "老村民",
                "text": "话语",
                "cooldown_seconds": 60,
            }
        )
