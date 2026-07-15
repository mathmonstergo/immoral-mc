from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo import __version__
from immortal_mmo.core.errors import DomainError


class HealthResponse(BaseModel):
    service: str
    status: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    migration_revision: str


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    ready: bool
    migration_revision: str | None = None


class ReadinessCheck(Protocol):
    async def __call__(self) -> ReadinessResult: ...


class ScriptDirectoryHeads(Protocol):
    def get_heads(self) -> list[str]: ...


class ServiceNotReadyError(DomainError):
    status_code = 503
    code = "service.not_ready"
    message = "The service is not ready."
    retryable = True


class PostgresReadinessChecker:
    def __init__(
        self,
        sessions: Callable[[], AsyncSession],
        script_directory: ScriptDirectoryHeads,
    ) -> None:
        self._sessions = sessions
        self._script_directory = script_directory

    async def __call__(self) -> ReadinessResult:
        try:
            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
                revisions = tuple(
                    (await session.execute(text("SELECT version_num FROM alembic_version")))
                    .scalars()
                    .all()
                )
            code_heads = tuple(self._script_directory.get_heads())
        except (OSError, SQLAlchemyError):
            return ReadinessResult(ready=False)

        if len(revisions) != 1 or len(code_heads) != 1 or revisions[0] != code_heads[0]:
            return ReadinessResult(ready=False)
        return ReadinessResult(ready=True, migration_revision=revisions[0])


async def not_configured_readiness() -> ReadinessResult:
    return ReadinessResult(ready=False)


def get_health() -> HealthResponse:
    return HealthResponse(
        service="game-service",
        status="ok",
        version=__version__,
    )
