from pydantic import BaseModel

from immortal_mmo import __version__


class HealthResponse(BaseModel):
    service: str
    status: str
    version: str


def get_health() -> HealthResponse:
    return HealthResponse(
        service="game-service",
        status="ok",
        version=__version__,
    )

