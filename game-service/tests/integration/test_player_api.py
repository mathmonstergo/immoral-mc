from uuid import UUID

from fastapi.testclient import TestClient

from immortal_mmo.main import create_app


def test_player_login_creates_account_and_current_life() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/players/login",
        json={
            "minecraft_uuid": "00000000-0000-0000-0000-000000000001",
            "player_name": "Sensen",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert UUID(body["account"]["account_id"])
    assert body["account"]["minecraft_uuid"] == "00000000-0000-0000-0000-000000000001"
    assert body["account"]["player_name"] == "Sensen"
    assert UUID(body["current_life"]["life_id"])
    assert body["current_life"]["account_id"] == body["account"]["account_id"]
    assert body["current_life"]["generation_no"] == 1
    assert body["current_life"]["status"] == "alive"
    assert body["current_life"]["spirit_root"] is None


def test_player_login_is_idempotent_for_minecraft_uuid() -> None:
    client = TestClient(create_app())
    payload = {
        "minecraft_uuid": "00000000-0000-0000-0000-000000000002",
        "player_name": "Repeat",
    }

    first = client.post("/api/v1/players/login", json=payload).json()
    second = client.post("/api/v1/players/login", json=payload).json()

    assert second["account"]["account_id"] == first["account"]["account_id"]
    assert second["current_life"]["life_id"] == first["current_life"]["life_id"]


def test_detect_spirit_root_assigns_structured_result_and_is_idempotent() -> None:
    client = TestClient(create_app())
    login = client.post(
        "/api/v1/players/login",
        json={
            "minecraft_uuid": "00000000-0000-0000-0000-000000000003",
            "player_name": "Detector",
        },
    ).json()
    account_id = login["account"]["account_id"]

    first = client.post(f"/api/v1/players/{account_id}/current-life/spirit-root")
    second = client.post(f"/api/v1/players/{account_id}/current-life/spirit-root")

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert first_body["life_id"] == login["current_life"]["life_id"]
    assert first_body["already_detected"] is False
    assert second_body["already_detected"] is True
    assert second_body["spirit_root"] == first_body["spirit_root"]
    assert set(first_body["spirit_root"]) == {
        "quality",
        "label",
        "elements",
        "mutated_element",
        "variant_element",
    }


def test_detect_spirit_root_for_unknown_account_returns_structured_error() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/players/00000000-0000-0000-0000-000000099999/current-life/spirit-root"
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "player.account_not_found",
            "message": "Player account was not found.",
            "retryable": False,
        }
    }

