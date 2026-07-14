from uuid import UUID

import httpx
import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.main import create_app


def client() -> httpx.AsyncClient:
    app = create_app(uow_factory=FakeUnitOfWorkFactory(FakeStore()))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def login(test_client: httpx.AsyncClient, suffix: int = 1) -> dict:
    response = await test_client.post(
        "/api/v1/players/login",
        json={"minecraft_uuid": str(UUID(int=suffix)), "player_name": f"Player{suffix}"},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_player_login_is_uuid_idempotent_and_keeps_current_payload() -> None:
    async with client() as test_client:
        first = await login(test_client)
        second = await login(test_client)

    assert second == first
    assert first["account"]["player_name"] == "Player1"
    assert first["current_life"]["status"] == "alive"
    assert first["current_life"]["spirit_root"] is None


@pytest.mark.asyncio
async def test_spirit_root_detection_is_immutable_and_presented_in_chinese() -> None:
    async with client() as test_client:
        player = await login(test_client, 2)
        path = (
            f"/api/v1/players/{player['account']['account_id']}"
            "/current-life/spirit-root"
        )

        first = await test_client.post(path)
        repeated = await test_client.post(path)

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert first.json()["already_detected"] is False
    assert repeated.json()["already_detected"] is True
    assert repeated.json()["spirit_root"] == first.json()["spirit_root"]
    assert set(first.json()["spirit_root"]) == {
        "quality",
        "label",
        "elements",
        "mutated_element",
        "variant_element",
    }


@pytest.mark.asyncio
async def test_unknown_account_uses_structured_domain_error_bytes() -> None:
    async with client() as test_client:
        response = await test_client.post(
            "/api/v1/players/00000000-0000-0000-0000-000000099999/current-life/spirit-root"
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "player.account_not_found"
