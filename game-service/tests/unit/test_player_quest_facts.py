from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.player.models import SpiritRootGenerator
from immortal_mmo.player.service import PlayerLifecycleError, PlayerService


class PostgreSqlDriverError(Exception):
    def __init__(self, sqlstate: str, constraint_name: str | None = None) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate
        self.constraint_name = constraint_name


class FailingUnitOfWork:
    def __init__(self, error: DBAPIError) -> None:
        self._error = error

    async def __aenter__(self) -> object:
        raise self._error

    async def __aexit__(self, *args: object) -> None:
        del args


class FailThenFakeUnitOfWorkFactory:
    def __init__(self, errors: list[DBAPIError]) -> None:
        self._errors = errors
        self._delegate = FakeUnitOfWorkFactory(FakeStore())
        self.calls = 0

    def __call__(self, *, isolation: str = "read_committed") -> object:
        self.calls += 1
        if self._errors:
            return FailingUnitOfWork(self._errors.pop(0))
        return self._delegate(isolation=isolation)


def db_error(sqlstate: str, constraint_name: str | None = None) -> DBAPIError:
    driver_error = PostgreSqlDriverError(sqlstate, constraint_name)
    wrapper = RuntimeError("asyncpg adapter wrapper")
    wrapper.__cause__ = driver_error
    return DBAPIError("statement", {}, wrapper)


@pytest.mark.asyncio
async def test_login_and_detection_use_transactional_player_facts() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    service = PlayerService(
        factory,
        spirit_root_generator=SpiritRootGenerator(
            roll=lambda: 0.95,
            choose_base_elements=lambda count: ("metal", "wood", "water", "fire", "earth")[
                :count
            ],
            choose_variant_pair=lambda: ("metal", "thunder"),
        ),
    )

    login = await service.login(UUID(int=1), "Facts")
    before = await service.get_current_life_facts(login.account.account_id)
    detected = await service.detect_current_life_spirit_root(login.account.account_id)
    repeated = await service.detect_current_life_spirit_root(login.account.account_id)
    after = await service.get_current_life_facts(login.account.account_id)

    assert before.spirit_root is None
    assert before.revision == 1
    assert detected.already_detected is False
    assert repeated.already_detected is True
    assert repeated.spirit_root == detected.spirit_root
    assert after.revision == 2
    assert factory.isolations == ["read_committed"] * 5


@pytest.mark.asyncio
async def test_historical_life_without_an_alive_life_is_a_lifecycle_error() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    service = PlayerService(factory)
    login = await service.login(UUID(int=2), "History")
    async with factory() as uow:
        life = await uow.players.get_current_life(login.account.account_id, for_update=True)
        assert life is not None
        uow._working_state.lives[life.life_id] = replace(life, status="reincarnated")
        await uow.commit()

    with pytest.raises(PlayerLifecycleError) as exc_info:
        await service.login(UUID(int=2), "History")

    assert exc_info.value.code == "player.lifecycle_unavailable"
    assert factory.isolations == ["read_committed"] * 3


@pytest.mark.asyncio
async def test_login_retries_complete_transaction_once_for_nested_retryable_sqlstate() -> None:
    factory = FailThenFakeUnitOfWorkFactory([db_error("40001")])
    service = PlayerService(factory)

    login = await service.login(UUID(int=3), "Retryable")

    assert login.account.minecraft_uuid == UUID(int=3)
    assert factory.calls == 2


@pytest.mark.asyncio
async def test_login_retries_named_final_unique_race_once_only() -> None:
    error = db_error("23505", "ux_lives_one_alive_per_account")
    factory = FailThenFakeUnitOfWorkFactory([error, error])
    service = PlayerService(factory)

    with pytest.raises(DBAPIError):
        await service.login(UUID(int=4), "UniqueRace")

    assert factory.calls == 2


@pytest.mark.asyncio
async def test_login_does_not_retry_unknown_unique_violation() -> None:
    factory = FailThenFakeUnitOfWorkFactory([db_error("23505", "some_other_constraint")])
    service = PlayerService(factory)

    with pytest.raises(DBAPIError):
        await service.login(UUID(int=5), "NoRetry")

    assert factory.calls == 1
