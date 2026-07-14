from dataclasses import replace
from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.player.models import SpiritRootGenerator
from immortal_mmo.player.service import PlayerLifecycleError, PlayerService


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
