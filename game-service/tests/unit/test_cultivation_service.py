from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.area_catalog import load_area_catalog
from immortal_mmo.cultivation.models import CultivationState, LifeTechnique, RealmEntry
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.player.service import PlayerService

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.mark.asyncio
async def test_start_and_settle_seclusion_consumes_only_retained_reserve() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=700), "Secluder")
    life_id = login.current_life.life_id
    technique_id = uuid4()
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        life_technique_id=technique_id,
        life_id=life_id,
        technique_id="GF_Fire_01",
        definition_version=1,
        group_code="qi",
        major_realm="练气",
        invested_amount=0,
        max_investment=100,
        current_layer=1,
        status="active",
    )
    factory.store._state.cultivation_balances[life_id] = 100
    factory.store._state.cultivation_states[life_id] = CultivationState(life_id, 1, 100, 0, None, 1)
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )

    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_id,),
        idempotency_key=uuid4(),
    )
    clock.now += timedelta(hours=1)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )

    assert settled.cumulative_retained == 10
    assert settled.cumulative_reserve_consumed == 10
    async with factory() as uow:
        state = await uow.cultivation.get_or_create_state(life_id, for_update=False)
        techniques = await uow.cultivation.get_techniques(
            life_id, (technique_id,), for_update=False
        )
    assert state.unrefined_cultivation == 90
    assert state.realized_cultivation == 10
    assert techniques[0].invested_amount == 10


@pytest.mark.asyncio
async def test_start_rejects_mixed_major_realm_selection() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=701), "Mixed")
    life_id = login.current_life.life_id
    ids = (uuid4(), uuid4())
    for technique_id, group, realm in (
        (ids[0], "qi", "练气"),
        (ids[1], "level:14", "筑基"),
    ):
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id, life_id, str(technique_id), 1, group, realm, 0, 100, 1, "active"
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )
    with pytest.raises(ValueError, match="same major realm"):
        await service.start_seclusion(
            account_id=login.account.account_id,
            area_id="neutral_training_ground",
            technique_ids=ids,
            idempotency_key=uuid4(),
        )


@pytest.mark.asyncio
async def test_start_seclusion_replays_same_request_for_same_idempotency_key() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=702), "Replay")
    life_id = login.current_life.life_id
    technique_ids = (UUID(int=7_022), UUID(int=7_021))
    for technique_id in technique_ids:
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            0,
            100,
            1,
            "active",
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )
    idempotency_key = uuid4()

    first = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=technique_ids,
        idempotency_key=idempotency_key,
    )
    replay = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=tuple(reversed(technique_ids)),
        idempotency_key=idempotency_key,
    )
    status = await service.seclusion_status(
        account_id=login.account.account_id,
        session_id=first.session_id,
    )

    assert replay == first
    assert status == first
    assert len(factory.store._state.cultivation_sessions) == 1


@pytest.mark.asyncio
async def test_start_seclusion_rejects_changed_request_for_same_idempotency_key() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=703), "Conflict")
    life_id = login.current_life.life_id
    technique_ids = (UUID(int=7_031), UUID(int=7_032))
    for technique_id in technique_ids:
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            0,
            100,
            1,
            "active",
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )
    idempotency_key = uuid4()
    await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_ids[0],),
        idempotency_key=idempotency_key,
    )

    with pytest.raises(ValueError, match="idempotency key was reused"):
        await service.start_seclusion(
            account_id=login.account.account_id,
            area_id="accelerated_cave",
            technique_ids=(technique_ids[1],),
            idempotency_key=idempotency_key,
        )


@pytest.mark.asyncio
async def test_shared_qi_settlement_advances_to_full_level_ten_and_stops() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=704), "QiBarrier")
    life_id = login.current_life.life_id
    technique_id = UUID(int=7_041)
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "GF_Qi_01",
        1,
        "qi",
        "练气",
        0,
        11_295,
        1,
        "active",
    )
    factory.store._state.cultivation_balances[life_id] = 11_293
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 1, 11_293, 0, None, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )
    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_id,),
        idempotency_key=uuid4(),
    )

    clock.now += timedelta(hours=10)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )
    snapshot = await service.current_life_snapshot(login.account.account_id)

    assert settled.status == "completed"
    assert settled.cumulative_retained == 11_293
    assert snapshot.current_level == 10
    assert snapshot.current_progress == 3_829
    assert snapshot.progress_full is True
    chain = tuple(factory.store._state.realm_entries.values())
    assert tuple(entry.target_level for entry in chain) == tuple(range(2, 11))


@pytest.mark.asyncio
async def test_exact_level_settlement_fills_bar_without_advancing() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=705), "FoundationBarrier")
    life_id = login.current_life.life_id
    technique_id = UUID(int=7_051)
    parent_entry_id = UUID(int=7_050)
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "GF_Foundation_01",
        1,
        "level:14",
        "筑基",
        0,
        43_931,
        1,
        "active",
    )
    factory.store._state.realm_entries[parent_entry_id] = RealmEntry(
        parent_entry_id,
        life_id,
        1,
        None,
        13,
        14,
        "qi",
        "level:14",
        9_420,
        0,
        "breakthrough",
        None,
        "active",
        None,
    )
    factory.store._state.cultivation_balances[life_id] = 43_931
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 14, 43_931, 0, None, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )
    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_id,),
        idempotency_key=uuid4(),
    )

    clock.now += timedelta(hours=20)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )
    snapshot = await service.current_life_snapshot(login.account.account_id)

    assert settled.status == "completed"
    assert snapshot.current_level == 14
    assert snapshot.current_progress == 43_931
    assert snapshot.progress_full is True
