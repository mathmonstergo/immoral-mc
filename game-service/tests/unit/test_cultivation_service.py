from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.cultivation.area_catalog import load_area_catalog
from immortal_mmo.cultivation.errors import (
    CultivationSeclusionConflictError,
    CultivationSeclusionRuleError,
)
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


async def _settle_two_techniques(
    *,
    account_seed: int,
    area_id: str,
    settlement_seconds: tuple[int, ...],
) -> tuple[tuple[int, int], int, int]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=account_seed), "SplitSettlement")
    life_id = login.current_life.life_id
    technique_ids = (UUID(int=account_seed * 10 + 1), UUID(int=account_seed * 10 + 2))
    for technique_id in technique_ids:
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            0,
            3_780,
            0,
            "active",
        )
    factory.store._state.cultivation_balances[life_id] = 100
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 1, 100, 0, None, 1
    )
    origin = datetime(2026, 7, 16, 8, tzinfo=UTC)
    clock = MutableClock(origin)
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )
    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id=area_id,
        technique_ids=technique_ids,
        idempotency_key=uuid4(),
    )

    settled = started
    for elapsed_seconds in settlement_seconds:
        clock.now = origin + timedelta(seconds=elapsed_seconds)
        settled = await service.settle_seclusion(
            account_id=login.account.account_id,
            session_id=started.session_id,
        )

    balances = tuple(
        factory.store._state.life_techniques[technique_id].invested_amount
        for technique_id in technique_ids
    )
    return balances, settled.cumulative_reserve_consumed, settled.cumulative_retained


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
        max_investment=3_780,
        current_layer=0,
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
    clock.now += timedelta(seconds=100)
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
async def test_mortal_seclusion_enters_level_one_through_ten_second_cycles() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=7_000), "Mortal")
    life_id = login.current_life.life_id
    technique_id = UUID(int=70_001)
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        life_technique_id=technique_id,
        life_id=life_id,
        technique_id="GF_YinqiShu_01",
        definition_version=1,
        group_code="qi",
        major_realm="练气",
        invested_amount=0,
        max_investment=3_780,
        current_layer=0,
        status="active",
    )
    factory.store._state.cultivation_balances[life_id] = 50
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 0, 50, 0, None, 1
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
    clock.now += timedelta(seconds=500)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )
    snapshot = await service.current_life_snapshot(login.account.account_id)

    assert settled.status == "active"
    assert settled.cumulative_generated == 50
    assert settled.cumulative_retained == 50
    assert snapshot.current_level == 1
    assert snapshot.realm_name == "练气一层"
    assert snapshot.current_progress == 0
    assert snapshot.max_exp == 100
    assert snapshot.realized_total == 50
    assert snapshot.unrefined_reserve == 0
    entries = tuple(factory.store._state.realm_entries.values())
    assert len(entries) == 1
    assert entries[0].source_level == 0
    assert entries[0].target_level == 1
    assert entries[0].source_floor == 50
    assert entries[0].target_baseline == 50


@pytest.mark.asyncio
async def test_start_rejects_different_groups_within_one_major_realm() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=701), "Mixed")
    life_id = login.current_life.life_id
    ids = (uuid4(), uuid4())
    for technique_id, group in zip(ids, ("level:14", "level:15"), strict=True):
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id, life_id, str(technique_id), 1, group, "筑基", 0, 100, 0, "active"
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )
    with pytest.raises(CultivationSeclusionRuleError, match="same technique group"):
        await service.start_seclusion(
            account_id=login.account.account_id,
            area_id="neutral_training_ground",
            technique_ids=ids,
            idempotency_key=uuid4(),
        )


@pytest.mark.asyncio
async def test_start_rejects_different_capacities_within_one_group() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=7_011), "MixedCapacity")
    life_id = login.current_life.life_id
    ids = (UUID(int=7_012), UUID(int=7_013))
    for technique_id, capacity in zip(ids, (3_780, 3_781), strict=True):
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            0,
            capacity,
            0,
            "active",
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )

    with pytest.raises(CultivationSeclusionRuleError, match="same capacity"):
        await service.start_seclusion(
            account_id=login.account.account_id,
            area_id="neutral_training_ground",
            technique_ids=ids,
            idempotency_key=uuid4(),
        )


@pytest.mark.asyncio
async def test_start_freezes_nascent_to_foundation_speed_and_area_multiplier() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=7_014), "NascentTrainer")
    life_id = login.current_life.life_id
    technique_id = UUID(int=7_015)
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "GF_Foundation_01",
        1,
        "level:14",
        "筑基",
        0,
        43_931,
        0,
        "active",
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 20, 0, 0, None, 1
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
        area_id="accelerated_cave",
        technique_ids=(technique_id,),
        idempotency_key=uuid4(),
    )
    frozen = factory.store._state.cultivation_sessions[started.session_id].frozen_snapshot

    assert started.completes_at - started.started_at == timedelta(seconds=10)
    assert frozen == {
        "area_version": 1,
        "cycle_seconds": 10,
        "technique_group": "level:14",
        "technique_capacity": 43_931,
        "full_mastery_seconds": 72_000,
        "base_cultivation_per_cycle": 6,
        "player_major_realm": "元婴",
        "player_speed_weight": 10,
        "technique_major_realm": "筑基",
        "technique_speed_weight": 2,
        "speed_basis_points": 20_000,
        "yield_basis_points": 10_000,
        "cultivation_per_cycle": 60,
    }
    assert factory.store._state.life_techniques[technique_id].max_investment == 43_931


@pytest.mark.asyncio
async def test_lower_realm_training_ignores_full_current_realm_barrier() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=7_016), "LowerRealmTraining")
    life_id = login.current_life.life_id
    selected_id = UUID(int=7_017)
    current_realm_id = UUID(int=7_018)
    factory.store._state.life_techniques[selected_id] = LifeTechnique(
        selected_id,
        life_id,
        "GF_Foundation_01",
        1,
        "level:14",
        "筑基",
        0,
        43_931,
        0,
        "active",
    )
    factory.store._state.life_techniques[current_realm_id] = LifeTechnique(
        current_realm_id,
        life_id,
        "GF_Nascent_01",
        1,
        "level:20",
        "元婴",
        9_678_780,
        9_678_780,
        13,
        "active",
    )
    factory.store._state.cultivation_balances[life_id] = 100
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 20, 100, 9_678_780, None, 1
    )
    origin = datetime(2026, 7, 16, 8, tzinfo=UTC)
    clock = MutableClock(origin)
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )
    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(selected_id,),
        idempotency_key=uuid4(),
    )

    clock.now = origin + timedelta(seconds=10)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )

    assert settled.status == "active"
    assert settled.cumulative_retained == 30
    assert factory.store._state.life_techniques[selected_id].invested_amount == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("selection_count", [1, 5])
async def test_selection_count_does_not_increase_total_cycle_speed(
    selection_count: int,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(
        UUID(int=7_020 + selection_count), "SelectionCount"
    )
    life_id = login.current_life.life_id
    technique_ids = tuple(UUID(int=7_100 + index) for index in range(selection_count))
    for technique_id in technique_ids:
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            0,
            3_780,
            0,
            "active",
        )
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
    )

    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=technique_ids,
        idempotency_key=uuid4(),
    )

    assert (
        factory.store._state.cultivation_sessions[started.session_id].frozen_snapshot[
            "cultivation_per_cycle"
        ]
        == 1
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("area_id", "expected"),
    [
        ("neutral_training_ground", ((1, 1), 2, 2)),
        ("rich_spirit_vein", ((1, 1), 2, 2)),
    ],
)
async def test_split_settlement_matches_one_combined_settlement(
    area_id: str,
    expected: tuple[tuple[int, int], int, int],
) -> None:
    combined = await _settle_two_techniques(
        account_seed=7_200,
        area_id=area_id,
        settlement_seconds=(20,),
    )
    split = await _settle_two_techniques(
        account_seed=7_201,
        area_id=area_id,
        settlement_seconds=(10, 20),
    )

    assert combined == split == expected


@pytest.mark.asyncio
async def test_rich_yield_can_fill_the_last_two_capacity_points_and_complete() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=7_202), "RichYieldMastery")
    life_id = login.current_life.life_id
    technique_ids = (UUID(int=72_021), UUID(int=72_022))
    for technique_id in technique_ids:
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            str(technique_id),
            1,
            "qi",
            "练气",
            3_779,
            3_780,
            12,
            "active",
        )
    factory.store._state.cultivation_balances[life_id] = 2
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 10, 2, 7_558, None, 1
    )
    origin = datetime(2026, 7, 16, 8, tzinfo=UTC)
    clock = MutableClock(origin)
    service = CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )
    started = await service.start_seclusion(
        account_id=login.account.account_id,
        area_id="rich_spirit_vein",
        technique_ids=technique_ids,
        idempotency_key=uuid4(),
    )

    clock.now = origin + timedelta(seconds=20)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )

    assert settled.status == "completed"
    assert settled.cumulative_reserve_consumed == 2
    assert settled.cumulative_retained == 2
    assert tuple(
        factory.store._state.life_techniques[technique_id].invested_amount
        for technique_id in technique_ids
    ) == (3_780, 3_780)


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
            0,
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
            0,
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

    with pytest.raises(CultivationSeclusionConflictError, match="idempotency key was reused"):
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
        11_343,
        0,
        "active",
    )
    factory.store._state.cultivation_balances[life_id] = 11_343
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 1, 11_343, 0, None, 1
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

    clock.now += timedelta(seconds=37_810)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )
    snapshot = await service.current_life_snapshot(login.account.account_id)

    assert settled.status == "completed"
    assert settled.cumulative_retained == 11_343
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
        0,
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

    clock.now += timedelta(seconds=73_220)
    settled = await service.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )
    snapshot = await service.current_life_snapshot(login.account.account_id)

    assert settled.status == "completed"
    assert snapshot.current_level == 14
    assert snapshot.current_progress == 43_931
    assert snapshot.progress_full is True


@pytest.mark.asyncio
async def test_learned_technique_snapshot_derives_name_and_layer_from_catalog() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=706), "TechniqueList")
    life_id = login.current_life.life_id
    technique_id = UUID(int=7_061)
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        technique_id,
        life_id,
        "Gongfa_68726c",
        1,
        "qi",
        "练气",
        3_780,
        3_780,
        13,
        "active",
    )

    snapshots = await CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
    ).list_techniques(login.account.account_id)

    assert len(snapshots) == 1
    assert snapshots[0].display_name == "冰冻术"
    assert snapshots[0].attribute_codes == ("water", "ice")
    assert snapshots[0].current_layer == 13
