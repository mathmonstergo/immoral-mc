from uuid import UUID

import pytest
from pydantic import ValidationError

from immortal_mmo.quest.schemas import QuestProviderRequest, QuestTurnInRequest


def test_accept_request_rejects_turn_in_inventory_identity_fields() -> None:
    with pytest.raises(ValidationError):
        QuestProviderRequest.model_validate(
            {
                "provider_id": "old-man",
                "inventory_item_instance_ids": [str(UUID(int=1))],
            }
        )


def test_turn_in_request_requires_explicit_inventory_identity_list() -> None:
    with pytest.raises(ValidationError):
        QuestTurnInRequest.model_validate({"provider_id": "old-man"})


def test_turn_in_request_rejects_duplicate_inventory_identities() -> None:
    item_id = UUID(int=1)
    with pytest.raises(ValidationError):
        QuestTurnInRequest(
            provider_id="old-man",
            inventory_item_instance_ids=[item_id, item_id],
        )
