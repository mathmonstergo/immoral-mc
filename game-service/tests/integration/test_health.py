import httpx
import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.main import create_app


@pytest.mark.asyncio
async def test_health_endpoint_reports_service_status() -> None:
    app = create_app(uow_factory=FakeUnitOfWorkFactory(FakeStore()))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "game-service",
        "status": "ok",
        "version": "0.1.0",
    }
