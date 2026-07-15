from __future__ import annotations

from collections.abc import Callable

import pytest
from tests.support import postgres

POSTGRES_17_ALPINE_IMAGE = (
    "postgres@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193"
)


@pytest.fixture(autouse=True)
def run_blocking_callbacks_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline(function: Callable[..., object], *args: object) -> object:
        return function(*args)

    monkeypatch.setattr(postgres.asyncio, "to_thread", inline)


class FakeContainer:
    def __init__(
        self,
        events: list[str],
        *,
        start_error: BaseException | None = None,
    ) -> None:
        self.events = events
        self.start_error = start_error

    def start(self) -> None:
        self.events.append("start")
        if self.start_error is not None:
            raise self.start_error

    def stop(self) -> None:
        self.events.append("stop")

    def get_connection_url(self) -> str:
        return "postgresql+psycopg2://test:test@127.0.0.1:5432/test"


class FakeResult:
    def scalar_one(self) -> str:
        return "17.6"


class FakeConnection:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def __aenter__(self) -> FakeConnection:
        self.events.append("connect")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        self.events.append("disconnect")

    async def execute(self, statement: object) -> FakeResult:
        self.events.append("version")
        return FakeResult()


class FakeEngine:
    def __init__(
        self,
        events: list[str],
        *,
        dispose_error: BaseException | None = None,
    ) -> None:
        self.events = events
        self.dispose_error = dispose_error

    def connect(self) -> FakeConnection:
        return FakeConnection(self.events)

    async def dispose(self) -> None:
        self.events.append("dispose")
        if self.dispose_error is not None:
            raise self.dispose_error


def _install_container(
    monkeypatch: pytest.MonkeyPatch,
    container: FakeContainer,
    captured_images: list[str],
) -> None:
    def factory(image: str) -> FakeContainer:
        captured_images.append(image)
        return container

    monkeypatch.setattr(postgres, "PostgresContainer", factory)


def _install_successful_engine(
    monkeypatch: pytest.MonkeyPatch,
    engine: FakeEngine,
) -> None:
    monkeypatch.setattr(postgres, "create_async_engine", lambda *args, **kwargs: engine)
    monkeypatch.setattr(postgres, "async_sessionmaker", lambda *args, **kwargs: object())


@pytest.mark.asyncio
async def test_container_stop_is_attempted_when_start_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured_images: list[str] = []
    start_error = RuntimeError("start failed")
    _install_container(
        monkeypatch,
        FakeContainer(events, start_error=start_error),
        captured_images,
    )

    with pytest.raises(RuntimeError, match="start failed"):
        async with postgres.migrated_postgres_container():
            raise AssertionError("container must not yield")

    assert events == ["start", "stop"]
    assert captured_images == [POSTGRES_17_ALPINE_IMAGE]


@pytest.mark.asyncio
async def test_container_stop_is_attempted_when_migration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured_images: list[str] = []
    migration_error = RuntimeError("migration failed")
    _install_container(monkeypatch, FakeContainer(events), captured_images)

    def fail_migration(database_url: str) -> None:
        events.append("migrate")
        raise migration_error

    monkeypatch.setattr(postgres, "_upgrade_to_head", fail_migration)

    with pytest.raises(RuntimeError, match="migration failed"):
        async with postgres.migrated_postgres_container():
            raise AssertionError("container must not yield")

    assert events == ["start", "migrate", "stop"]


@pytest.mark.asyncio
async def test_container_stop_is_attempted_when_engine_dispose_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured_images: list[str] = []
    dispose_error = RuntimeError("dispose failed")
    _install_container(monkeypatch, FakeContainer(events), captured_images)
    monkeypatch.setattr(
        postgres,
        "_upgrade_to_head",
        lambda database_url: events.append("migrate"),
    )
    _install_successful_engine(
        monkeypatch,
        FakeEngine(events, dispose_error=dispose_error),
    )

    with pytest.raises(RuntimeError, match="dispose failed"):
        async with postgres.migrated_postgres_container():
            events.append("yield")

    assert events[-2:] == ["dispose", "stop"]
