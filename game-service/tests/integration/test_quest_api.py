import inspect
from uuid import UUID

from fastapi.testclient import TestClient

from immortal_mmo.main import create_app
from immortal_mmo.player.service import PlayerService
from immortal_mmo.quest.api import (
    accept_quest,
    get_quest_interaction_state,
    turn_in_quest,
)
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import QuestProviderDefinition
from immortal_mmo.quest.repository import InMemoryQuestRepository
from immortal_mmo.quest.service import QuestService


def test_quest_handlers_are_synchronous_for_fastapi_threadpool_dispatch() -> None:
    assert inspect.iscoroutinefunction(get_quest_interaction_state) is False
    assert inspect.iscoroutinefunction(accept_quest) is False
    assert inspect.iscoroutinefunction(turn_in_quest) is False


def login(client: TestClient, suffix: int = 1) -> dict:
    return client.post(
        "/api/v1/players/login",
        json={
            "minecraft_uuid": str(UUID(int=suffix)),
            "player_name": f"Quest{suffix}",
        },
    ).json()


def test_inspect_returns_exact_available_interaction_contract_and_deduplicates() -> None:
    client = TestClient(create_app())
    player = login(client)
    account_id = player["account"]["account_id"]

    response = client.post(
        f"/api/v1/players/{account_id}/current-life/quest-interaction-state",
        json={"provider_ids": ["old-man", "old-man"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "contract_version": 1,
        "account_id": account_id,
        "life_id": player["current_life"]["life_id"],
        "revision": {
            "player": 1,
            "quest": 0,
            "definitions": QUEST_CATALOG.revision,
        },
        "providers": [
            {
                "provider_id": "old-man",
                "state_key": "first-steps:available",
                "quests": [
                    {
                        "quest_id": "first-steps",
                        "title": "初入凡尘",
                        "category": "main",
                        "state": "available",
                        "action": "offer",
                        "dialogue_key": "first-steps.available",
                        "objectives": [
                            {
                                "objective_id": "detect-spirit-root",
                                "title": "灵根检测",
                                "current": 0,
                                "required": 1,
                                "completed": False,
                            }
                        ],
                    }
                ],
                "actionable_quest_ids": ["first-steps"],
                "direct_action_quest_id": "first-steps",
                "proximity_bark": {
                    "key": "first-steps:available",
                    "text": "最近太不太平了...",
                    "cooldown_seconds": 60,
                },
            }
        ],
        "tracked_quest": None,
        "cache_ttl_ms": 2000,
    }


def test_inspect_rejects_more_than_32_deduplicated_providers() -> None:
    client = TestClient(create_app())
    account_id = login(client, 2)["account"]["account_id"]

    response = client.post(
        f"/api/v1/players/{account_id}/current-life/quest-interaction-state",
        json={"provider_ids": [f"provider-{index}" for index in range(33)]},
    )

    assert response.status_code == 422


def test_inspect_applies_provider_cap_after_deduplication() -> None:
    client = TestClient(create_app())
    account_id = login(client, 20)["account"]["account_id"]

    response = client.post(
        f"/api/v1/players/{account_id}/current-life/quest-interaction-state",
        json={"provider_ids": ["old-man"] * 33},
    )

    assert response.status_code == 200
    assert [provider["provider_id"] for provider in response.json()["providers"]] == [
        "old-man"
    ]


def test_mutation_requires_uuid_idempotency_key() -> None:
    client = TestClient(create_app())
    account_id = login(client, 3)["account"]["account_id"]
    path = f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept"

    missing = client.put(path, json={"provider_id": "old-man"})
    missing_body = client.put(
        path,
        headers={"Idempotency-Key": str(UUID(int=301))},
    )
    malformed = client.put(
        path,
        headers={"Idempotency-Key": "not-a-uuid"},
        json={"provider_id": "old-man"},
    )

    assert missing.status_code == 422
    assert missing_body.status_code == 422
    assert malformed.status_code == 422


def test_full_quest_loop_and_semantic_mutation_noops() -> None:
    client = TestClient(create_app())
    player = login(client, 4)
    account_id = player["account"]["account_id"]
    accept_path = (
        f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept"
    )
    turn_in_path = (
        f"/api/v1/players/{account_id}/current-life/quests/first-steps/turn-in"
    )

    accepted = client.put(
        accept_path,
        headers={"Idempotency-Key": str(UUID(int=401))},
        json={"provider_id": "old-man"},
    )
    repeated_accept = client.put(
        accept_path,
        headers={"Idempotency-Key": str(UUID(int=402))},
        json={"provider_id": "old-man"},
    )

    assert accepted.status_code == 200
    assert accepted.json()["changed"] is True
    assert accepted.json()["quest"]["state"] == "active"
    assert accepted.json()["interaction_state"]["tracked_quest"]["objectives"][0][
        "current"
    ] == 0
    assert repeated_accept.status_code == 200
    assert repeated_accept.json()["changed"] is False
    assert repeated_accept.json()["interaction_state"]["revision"]["quest"] == 1

    replayed_accept = client.put(
        accept_path,
        headers={"Idempotency-Key": str(UUID(int=401))},
        json={"provider_id": "old-man"},
    )
    assert replayed_accept.json() == accepted.json()

    detected = client.post(
        f"/api/v1/players/{account_id}/current-life/spirit-root"
    )
    inspected_ready = client.post(
        f"/api/v1/players/{account_id}/current-life/quest-interaction-state",
        json={"provider_ids": ["old-man"]},
    )

    assert detected.status_code == 200
    assert inspected_ready.json()["providers"][0]["quests"][0]["state"] == (
        "ready_to_turn_in"
    )
    assert inspected_ready.json()["tracked_quest"]["next_action_hint"] == "返回老村民处"
    assert inspected_ready.json()["revision"]["player"] == 2
    assert inspected_ready.json()["revision"]["quest"] == 1

    completed = client.put(
        turn_in_path,
        headers={"Idempotency-Key": str(UUID(int=403))},
        json={"provider_id": "old-man"},
    )
    repeated_turn_in = client.put(
        turn_in_path,
        headers={"Idempotency-Key": str(UUID(int=404))},
        json={"provider_id": "old-man"},
    )

    assert completed.status_code == 200
    assert completed.json()["changed"] is True
    assert completed.json()["quest"]["state"] == "completed"
    assert completed.json()["interaction_state"]["tracked_quest"] is None
    assert repeated_turn_in.status_code == 200
    assert repeated_turn_in.json()["changed"] is False
    assert repeated_turn_in.json()["interaction_state"]["revision"]["quest"] == 2

    replayed_after_completion = client.put(
        accept_path,
        headers={"Idempotency-Key": str(UUID(int=401))},
        json={"provider_id": "old-man"},
    )
    assert replayed_after_completion.json() == accepted.json()


def test_operation_conflict_returns_exact_domain_error() -> None:
    client = TestClient(create_app())
    account_id = login(client, 5)["account"]["account_id"]
    operation_id = str(UUID(int=501))
    headers = {"Idempotency-Key": operation_id}
    body = {"provider_id": "old-man"}
    base = f"/api/v1/players/{account_id}/current-life/quests/first-steps"
    client.put(f"{base}/accept", headers=headers, json=body)
    client.post(f"/api/v1/players/{account_id}/current-life/spirit-root")

    response = client.put(f"{base}/turn-in", headers=headers, json=body)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "quest.idempotency_conflict",
            "message": "Idempotency key was already used for a different operation.",
            "retryable": False,
        }
    }


def test_operation_conflict_precedes_unknown_target_over_http() -> None:
    client = TestClient(create_app())
    account_id = login(client, 50)["account"]["account_id"]
    operation_id = str(UUID(int=502))
    headers = {"Idempotency-Key": operation_id}
    client.put(
        f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept",
        headers=headers,
        json={"provider_id": "old-man"},
    )

    response = client.put(
        f"/api/v1/players/{account_id}/current-life/quests/missing/turn-in",
        headers=headers,
        json={"provider_id": "missing"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "quest.idempotency_conflict"


def test_major_quest_errors_use_domain_error_envelope() -> None:
    client = TestClient(create_app())
    account_id = login(client, 51)["account"]["account_id"]
    base = f"/api/v1/players/{account_id}/current-life/quests"

    unknown_quest = client.put(
        f"{base}/missing/accept",
        headers={"Idempotency-Key": str(UUID(int=510))},
        json={"provider_id": "old-man"},
    )
    unknown_provider = client.put(
        f"{base}/first-steps/accept",
        headers={"Idempotency-Key": str(UUID(int=511))},
        json={"provider_id": "missing"},
    )
    not_accepted = client.put(
        f"{base}/first-steps/turn-in",
        headers={"Idempotency-Key": str(UUID(int=512))},
        json={"provider_id": "old-man"},
    )
    client.put(
        f"{base}/first-steps/accept",
        headers={"Idempotency-Key": str(UUID(int=513))},
        json={"provider_id": "old-man"},
    )
    not_ready = client.put(
        f"{base}/first-steps/turn-in",
        headers={"Idempotency-Key": str(UUID(int=514))},
        json={"provider_id": "old-man"},
    )

    assert (unknown_quest.status_code, unknown_quest.json()) == (
        404,
        {
            "error": {
                "code": "quest.not_found",
                "message": "Quest was not found.",
                "retryable": False,
            }
        },
    )
    assert (unknown_provider.status_code, unknown_provider.json()) == (
        404,
        {
            "error": {
                "code": "quest.provider_not_found",
                "message": "Quest provider was not found.",
                "retryable": False,
            }
        },
    )
    assert (not_accepted.status_code, not_accepted.json()) == (
        409,
        {
            "error": {
                "code": "quest.not_accepted",
                "message": "Quest has not been accepted.",
                "retryable": False,
            }
        },
    )
    assert (not_ready.status_code, not_ready.json()) == (
        409,
        {
            "error": {
                "code": "quest.not_ready",
                "message": "Quest objectives are not complete.",
                "retryable": False,
            }
        },
    )


def test_provider_mismatch_returns_exact_domain_error() -> None:
    player_service = PlayerService()
    catalog = QuestDefinitionCatalog(
        quests=(QUEST_CATALOG.get_quest("first-steps"),),
        providers=(
            QUEST_CATALOG.get_provider("old-man"),
            QuestProviderDefinition(
                provider_id="other",
                display_name="Other",
                main_quest_ids=(),
                side_quest_ids=(),
            ),
        ),
    )
    quest_service = QuestService(player_service, InMemoryQuestRepository(), catalog)
    client = TestClient(create_app(player_service=player_service, quest_service=quest_service))
    account_id = login(client, 6)["account"]["account_id"]

    response = client.put(
        f"/api/v1/players/{account_id}/current-life/quests/first-steps/accept",
        headers={"Idempotency-Key": str(UUID(int=601))},
        json={"provider_id": "other"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "quest.provider_mismatch",
            "message": "Quest is not available from this provider.",
            "retryable": False,
        }
    }
