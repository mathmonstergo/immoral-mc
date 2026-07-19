from uuid import UUID

import pytest
from pydantic import ValidationError

from immortal_mmo.storage.schemas import StorageMoveRequest


def test_storage_move_request_rejects_client_supplied_result_fields() -> None:
    with pytest.raises(ValidationError):
        StorageMoveRequest.model_validate(
            {
                "move_kind": "deposit",
                "item_instance_id": str(UUID(int=1)),
                "expected_revision": 0,
                "destination_page": 1,
                "destination_slot": 0,
                "view_page": 1,
                "resulting_revision": 1,
            }
        )
