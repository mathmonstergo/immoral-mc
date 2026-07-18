from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.core.errors import ConflictError
from immortal_mmo.cultivation.models import (
    CultivationSession,
    CultivationState,
    LifeTechnique,
    RealmEntry,
)
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.player.service import PlayerService

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def service(
    factory: FakeUnitOfWorkFactory,
    *,
    clock: MutableClock | None = None,
) -> CultivationService:
    return CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        clock=clock,
    )


def technique(
    *,
    technique_id: UUID,
    life_id: UUID,
    group: str,
    realm: str,
    invested: int,
    capacity: int,
) -> LifeTechnique:
    return LifeTechnique(
        life_technique_id=technique_id,
        life_id=life_id,
        technique_id=f"GF_Test_{technique_id.int}",
        definition_version=1,
        group_code=group,
        major_realm=realm,
        invested_amount=invested,
        max_investment=capacity,
        current_layer=1,
        status="active",
    )


def append_entry(
    factory: FakeUnitOfWorkFactory,
    *,
    life_id: UUID,
    generation: int,
    parent: RealmEntry | None,
    source_level: int,
    target_level: int,
    source_group: str,
    target_group: str,
    source_floor: int,
    target_baseline: int,
    transition_kind: str = "adjacent",
) -> RealmEntry:
    entry = RealmEntry(
        realm_entry_id=UUID(int=80_000 + generation),
        life_id=life_id,
        generation=generation,
        parent_entry_id=None if parent is None else parent.realm_entry_id,
        source_level=source_level,
        target_level=target_level,
        source_group=source_group,
        target_group=target_group,
        source_floor=source_floor,
        target_baseline=target_baseline,
        transition_kind=transition_kind,
        transition_session_id=None,
        status="active",
        invalidated_at=None,
    )
    factory.store._state.realm_entries[entry.realm_entry_id] = entry
    return entry


@pytest.mark.asyncio
async def test_abandonment_debits_exact_investment_and_crosses_major_realm() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=8_001), "Regressor")
    life_id = login.current_life.life_id
    kept_qi_id = UUID(int=8_011)
    abandoned_qi_id = UUID(int=8_012)
    foundation_id = UUID(int=8_013)
    factory.store._state.life_techniques[kept_qi_id] = technique(
        technique_id=kept_qi_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=10_000,
        capacity=20_000,
    )
    factory.store._state.life_techniques[abandoned_qi_id] = technique(
        technique_id=abandoned_qi_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=2_000,
        capacity=20_000,
    )
    factory.store._state.life_techniques[foundation_id] = technique(
        technique_id=foundation_id,
        life_id=life_id,
        group="level:14",
        realm="筑基",
        invested=7_000,
        capacity=43_931,
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 14, 777, 19_000, None, 1
    )

    catalog = load_realm_catalog(ROOT / "realm_catalog.json")
    totals = catalog.qi_cumulative_totals()
    parent = None
    for source_level in range(1, 10):
        parent = append_entry(
            factory,
            life_id=life_id,
            generation=source_level,
            parent=parent,
            source_level=source_level,
            target_level=source_level + 1,
            source_group="qi",
            target_group="qi",
            source_floor=totals[source_level],
            target_baseline=totals[source_level],
        )
    breakthrough = append_entry(
        factory,
        life_id=life_id,
        generation=10,
        parent=parent,
        source_level=10,
        target_level=14,
        source_group="qi",
        target_group="level:14",
        source_floor=totals[10],
        target_baseline=7_000,
        transition_kind="breakthrough",
    )
    idempotency_key = UUID(int=8_099)

    first = await service(factory).abandon_technique(
        account_id=login.account.account_id,
        life_technique_id=abandoned_qi_id,
        idempotency_key=idempotency_key,
    )
    replay = await service(factory).abandon_technique(
        account_id=login.account.account_id,
        life_technique_id=abandoned_qi_id,
        idempotency_key=idempotency_key,
    )

    assert replay == first
    assert first.operation_kind == "abandonment"
    assert first.removed_amount == 2_000
    assert first.transferred_amount == 0
    assert first.destroyed_amount == 2_000
    assert first.cultivation.current_level == 10
    assert first.cultivation.realized_total == 17_000
    assert first.cultivation.unrefined_reserve == 777
    stored_source = factory.store._state.life_techniques[abandoned_qi_id]
    assert stored_source.status == "abandoned"
    assert stored_source.invested_amount == 0
    assert factory.store._state.life_techniques[foundation_id].invested_amount == 7_000
    assert factory.store._state.realm_entries[breakthrough.realm_entry_id].status == "invalidated"

    with pytest.raises(ConflictError, match="idempotency"):
        await service(factory).abandon_technique(
            account_id=login.account.account_id,
            life_technique_id=kept_qi_id,
            idempotency_key=idempotency_key,
        )


@pytest.mark.asyncio
async def test_reentry_uses_new_generation_and_never_revives_invalidated_branch() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=8_101), "Reentry")
    life_id = login.current_life.life_id
    abandoned_id = UUID(int=8_111)
    retained_id = UUID(int=8_112)
    factory.store._state.life_techniques[abandoned_id] = technique(
        technique_id=abandoned_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=100,
        capacity=109,
    )
    factory.store._state.life_techniques[retained_id] = technique(
        technique_id=retained_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=150,
        capacity=251,
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 3, 100, 250, None, 1
    )
    first_entry = append_entry(
        factory,
        life_id=life_id,
        generation=1,
        parent=None,
        source_level=1,
        target_level=2,
        source_group="qi",
        target_group="qi",
        source_floor=100,
        target_baseline=100,
    )
    invalidated_entry = append_entry(
        factory,
        life_id=life_id,
        generation=2,
        parent=first_entry,
        source_level=2,
        target_level=3,
        source_group="qi",
        target_group="qi",
        source_floor=250,
        target_baseline=250,
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    cultivation = service(factory, clock=clock)

    regressed = await cultivation.abandon_technique(
        account_id=login.account.account_id,
        life_technique_id=abandoned_id,
        idempotency_key=UUID(int=8_190),
    )
    assert regressed.cultivation.current_level == 2
    assert factory.store._state.realm_entries[invalidated_entry.realm_entry_id].status == (
        "invalidated"
    )

    started = await cultivation.start_seclusion(
        account_id=login.account.account_id,
        area_id="neutral_training_ground",
        technique_ids=(retained_id,),
        idempotency_key=UUID(int=8_191),
    )
    clock.now += timedelta(hours=4)
    await cultivation.settle_seclusion(
        account_id=login.account.account_id,
        session_id=started.session_id,
    )

    entries = sorted(factory.store._state.realm_entries.values(), key=lambda item: item.generation)
    new_entry = entries[-1]
    assert new_entry.generation == 3
    assert new_entry.parent_entry_id == first_entry.realm_entry_id
    assert new_entry.transition_kind == "reentry"
    assert invalidated_entry.status == "active"
    assert factory.store._state.realm_entries[invalidated_entry.realm_entry_id].status == (
        "invalidated"
    )
    assert factory.store._state.cultivation_states[life_id].current_level == 3


@pytest.mark.asyncio
async def test_transfer_preserves_configured_fraction_bounded_by_target_capacity() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=8_201), "Transfer")
    life_id = login.current_life.life_id
    source_id = UUID(int=8_211)
    target_id = UUID(int=8_212)
    factory.store._state.life_techniques[source_id] = technique(
        technique_id=source_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=101,
        capacity=201,
    )
    factory.store._state.life_techniques[target_id] = technique(
        technique_id=target_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=78,
        capacity=109,
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 1, 55, 179, None, 1
    )
    cultivation = service(factory)
    idempotency_key = UUID(int=8_299)

    first = await cultivation.transfer_technique(
        account_id=login.account.account_id,
        source_technique_id=source_id,
        target_technique_id=target_id,
        transfer_profile_id="Trans_Gongfa_01",
        idempotency_key=idempotency_key,
    )
    replay = await cultivation.transfer_technique(
        account_id=login.account.account_id,
        source_technique_id=source_id,
        target_technique_id=target_id,
        transfer_profile_id="Trans_Gongfa_01",
        idempotency_key=idempotency_key,
    )

    assert replay == first
    assert first.operation_kind == "transfer"
    assert first.removed_amount == 101
    assert first.transferred_amount == 31
    assert first.destroyed_amount == 70
    assert first.cultivation.realized_total == 109
    assert first.cultivation.unrefined_reserve == 55
    assert factory.store._state.life_techniques[source_id].status == "abandoned"
    assert factory.store._state.life_techniques[source_id].invested_amount == 0
    assert factory.store._state.life_techniques[target_id].invested_amount == 109


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["abandon", "transfer"])
@pytest.mark.parametrize(
    ("session_kind", "status", "message"),
    [
        ("breakthrough", "pending", "breakthrough"),
        ("ordinary", "active", "seclusion"),
    ],
)
async def test_open_cultivation_session_rejects_technique_mutation(
    operation: str,
    session_kind: str,
    status: str,
    message: str,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=8_301), "Blocked")
    life_id = login.current_life.life_id
    source_id = UUID(int=8_311)
    target_id = UUID(int=8_312)
    factory.store._state.life_techniques[source_id] = technique(
        technique_id=source_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=10,
        capacity=100,
    )
    factory.store._state.life_techniques[target_id] = technique(
        technique_id=target_id,
        life_id=life_id,
        group="qi",
        realm="练气",
        invested=0,
        capacity=100,
    )
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    session_id = UUID(int=8_390)
    factory.store._state.cultivation_sessions[session_id] = CultivationSession(
        session_id=session_id,
        life_id=life_id,
        session_kind=session_kind,
        status=status,
        idempotency_key=UUID(int=8_391),
        request_fingerprint="0" * 64,
        area_id="neutral_training_ground" if session_kind == "ordinary" else None,
        content_version=f"{session_kind}:v1",
        source_level=10,
        target_level=14 if session_kind == "breakthrough" else None,
        frozen_snapshot={},
        cumulative_elapsed_seconds=0,
        cumulative_generated=0,
        cumulative_reserve_consumed=0,
        cumulative_retained=0,
        started_at=now,
        completes_at=now + timedelta(minutes=10),
        settled_at=None,
        revision=1,
    )
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id, 10, 44, 10, session_id, 1
    )
    cultivation = service(factory)

    with pytest.raises(ConflictError, match=message):
        if operation == "abandon":
            await cultivation.abandon_technique(
                account_id=login.account.account_id,
                life_technique_id=source_id,
                idempotency_key=uuid4(),
            )
        else:
            await cultivation.transfer_technique(
                account_id=login.account.account_id,
                source_technique_id=source_id,
                target_technique_id=target_id,
                transfer_profile_id="Trans_Gongfa_01",
                idempotency_key=uuid4(),
            )
