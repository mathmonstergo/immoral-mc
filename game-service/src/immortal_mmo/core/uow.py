from types import TracebackType
from typing import Literal, Protocol

from immortal_mmo.player.repository import PlayerRepository
from immortal_mmo.quest.repository import QuestRepository

IsolationLevel = Literal["read_committed", "repeatable_read"]


class UnitOfWork(Protocol):
    players: PlayerRepository
    quests: QuestRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(
        self,
        *,
        isolation: IsolationLevel = "read_committed",
    ) -> UnitOfWork: ...
