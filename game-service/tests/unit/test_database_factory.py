import pytest

from immortal_mmo.core.config import Settings
from immortal_mmo.db.base import NAMING_CONVENTION, Base
from immortal_mmo.db.session import create_engine, create_session_factory
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory


def test_base_uses_stable_constraint_naming_convention() -> None:
    assert NAMING_CONVENTION == {
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
    assert Base.metadata.naming_convention == NAMING_CONVENTION


def test_create_engine_forwards_strict_database_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_engine = object()
    captured: dict[str, object] = {}

    def recording_create_async_engine(url: str, **options: object) -> object:
        captured["url"] = url
        captured.update(options)
        return sentinel_engine

    monkeypatch.setattr(
        "immortal_mmo.db.session.create_async_engine",
        recording_create_async_engine,
    )
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://game:test@database/game",
        database_pool_size=7,
        database_max_overflow=13,
        database_pool_timeout_seconds=4.5,
        database_echo=True,
    )

    engine = create_engine(settings)

    assert engine is sentinel_engine
    assert captured == {
        "url": "postgresql+asyncpg://game:test@database/game",
        "echo": True,
        "pool_pre_ping": True,
        "pool_size": 7,
        "max_overflow": 13,
        "pool_timeout": 4.5,
    }


def test_create_session_factory_disables_implicit_state_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_engine = object()
    sentinel_factory = object()
    captured: dict[str, object] = {}

    def recording_async_sessionmaker(engine: object, **options: object) -> object:
        captured["engine"] = engine
        captured.update(options)
        return sentinel_factory

    monkeypatch.setattr(
        "immortal_mmo.db.session.async_sessionmaker",
        recording_async_sessionmaker,
    )

    factory = create_session_factory(sentinel_engine)

    assert factory is sentinel_factory
    assert captured == {
        "engine": sentinel_engine,
        "expire_on_commit": False,
        "autoflush": False,
    }


class RecordingSession:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.transaction_active = False

    async def connection(self, *, execution_options: dict[str, str]) -> object:
        self.events.append(f"connection:{execution_options['isolation_level']}")
        self.transaction_active = True
        return object()

    async def begin(self) -> None:
        raise AssertionError("session.connection() already started the transaction")

    async def commit(self) -> None:
        self.events.append("commit")
        self.transaction_active = False

    async def rollback(self) -> None:
        self.events.append("rollback")
        self.transaction_active = False

    async def close(self) -> None:
        self.events.append("close")

    def in_transaction(self) -> bool:
        return self.transaction_active


class RecordingSessionFactory:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.sessions: list[RecordingSession] = []

    def __call__(self) -> RecordingSession:
        self.events.append("session")
        session = RecordingSession(self.events)
        self.sessions.append(session)
        return session


class RecordingRepositoryFactory:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.repository: object | None = None
        self.session: RecordingSession | None = None

    def __call__(self, session: RecordingSession) -> object:
        self.events.append(self.name)
        self.repository = object()
        self.session = session
        return self.repository


def make_uow_factory(
    events: list[str],
) -> tuple[
    SqlAlchemyUnitOfWorkFactory,
    RecordingSessionFactory,
    RecordingRepositoryFactory,
    RecordingRepositoryFactory,
]:
    sessions = RecordingSessionFactory(events)
    players = RecordingRepositoryFactory("players", events)
    quests = RecordingRepositoryFactory("quests", events)
    return SqlAlchemyUnitOfWorkFactory(sessions, players, quests), sessions, players, quests


@pytest.mark.asyncio
async def test_uow_configures_default_isolation_before_binding_shared_session() -> None:
    events: list[str] = []
    factory, sessions, players, quests = make_uow_factory(events)

    async with factory() as uow:
        session = sessions.sessions[0]

        assert events == ["session", "connection:READ COMMITTED", "players", "quests"]
        assert (players.repository, players.session) == (uow.players, session)
        assert (quests.repository, quests.session) == (uow.quests, session)
        await uow.commit()
        assert session.in_transaction() is False

    assert events == [
        "session",
        "connection:READ COMMITTED",
        "players",
        "quests",
        "commit",
        "close",
    ]


@pytest.mark.asyncio
async def test_uow_maps_repeatable_read_without_starting_a_second_transaction() -> None:
    events: list[str] = []
    factory, _, _, _ = make_uow_factory(events)

    async with factory(isolation="repeatable_read") as uow:
        await uow.rollback()

    assert events == [
        "session",
        "connection:REPEATABLE READ",
        "players",
        "quests",
        "rollback",
        "close",
    ]


@pytest.mark.asyncio
async def test_uow_rolls_back_and_closes_when_context_raises() -> None:
    events: list[str] = []
    factory, _, _, _ = make_uow_factory(events)

    with pytest.raises(RuntimeError, match="boom"):
        async with factory():
            raise RuntimeError("boom")

    assert events == [
        "session",
        "connection:READ COMMITTED",
        "players",
        "quests",
        "rollback",
        "close",
    ]


@pytest.mark.asyncio
async def test_uow_rolls_back_uncommitted_successful_context() -> None:
    events: list[str] = []
    factory, _, _, _ = make_uow_factory(events)

    async with factory():
        pass

    assert events[-2:] == ["rollback", "close"]
