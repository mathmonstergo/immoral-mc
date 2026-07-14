from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.core.uow import IsolationLevel
from immortal_mmo.player.repository import PlayerRepository
from immortal_mmo.quest.repository import QuestRepository

PlayerRepositoryFactory = Callable[[AsyncSession], PlayerRepository]
QuestRepositoryFactory = Callable[[AsyncSession], QuestRepository]

ISOLATION_LEVELS: dict[IsolationLevel, str] = {
    "read_committed": "READ COMMITTED",
    "repeatable_read": "REPEATABLE READ",
}


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        isolation: IsolationLevel,
        player_repository_factory: PlayerRepositoryFactory,
        quest_repository_factory: QuestRepositoryFactory,
    ) -> None:
        self._sessions = sessions
        self._isolation = isolation
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._sessions()
        await self.session.connection(
            execution_options={"isolation_level": ISOLATION_LEVELS[self._isolation]}
        )
        self.players = self._player_repository_factory(self.session)
        self.quests = self._quest_repository_factory(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self.session.in_transaction():
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class SqlAlchemyUnitOfWorkFactory:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        player_repository_factory: PlayerRepositoryFactory,
        quest_repository_factory: QuestRepositoryFactory,
    ) -> None:
        self._sessions = sessions
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory

    def __call__(
        self,
        *,
        isolation: IsolationLevel = "read_committed",
    ) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(
            self._sessions,
            isolation,
            self._player_repository_factory,
            self._quest_repository_factory,
        )
