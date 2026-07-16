from collections.abc import Callable
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from immortal_mmo.combat.repository import CombatRepository
from immortal_mmo.core.uow import IsolationLevel
from immortal_mmo.cultivation.repository import CultivationRepository
from immortal_mmo.item.repository import ItemRepository
from immortal_mmo.player.repository import PlayerRepository
from immortal_mmo.quest.repository import QuestRepository

PlayerRepositoryFactory = Callable[[AsyncSession], PlayerRepository]
QuestRepositoryFactory = Callable[[AsyncSession], QuestRepository]
CombatRepositoryFactory = Callable[[AsyncSession], CombatRepository]
CultivationRepositoryFactory = Callable[[AsyncSession], CultivationRepository]
ItemRepositoryFactory = Callable[[AsyncSession], ItemRepository]

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
        combat_repository_factory: CombatRepositoryFactory,
        cultivation_repository_factory: CultivationRepositoryFactory,
        item_repository_factory: ItemRepositoryFactory,
    ) -> None:
        self._sessions = sessions
        self._isolation = isolation
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory
        self._combat_repository_factory = combat_repository_factory
        self._cultivation_repository_factory = cultivation_repository_factory
        self._item_repository_factory = item_repository_factory

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._sessions()
        try:
            await self.session.connection(
                execution_options={"isolation_level": ISOLATION_LEVELS[self._isolation]}
            )
            self.players = self._player_repository_factory(self.session)
            self.quests = self._quest_repository_factory(self.session)
            self.combat = self._combat_repository_factory(self.session)
            self.cultivation = self._cultivation_repository_factory(self.session)
            self.items = self._item_repository_factory(self.session)
            return self
        except BaseException:
            await self._rollback_and_close()
            raise

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._rollback_and_close()

    async def _rollback_and_close(self) -> None:
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
        combat_repository_factory: CombatRepositoryFactory,
        cultivation_repository_factory: CultivationRepositoryFactory,
        item_repository_factory: ItemRepositoryFactory,
    ) -> None:
        self._sessions = sessions
        self._player_repository_factory = player_repository_factory
        self._quest_repository_factory = quest_repository_factory
        self._combat_repository_factory = combat_repository_factory
        self._cultivation_repository_factory = cultivation_repository_factory
        self._item_repository_factory = item_repository_factory

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
            self._combat_repository_factory,
            self._cultivation_repository_factory,
            self._item_repository_factory,
        )
