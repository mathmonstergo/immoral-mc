from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from tests.support.fakes import FakeCultivationRepository, FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.core.errors import ConflictError, DomainError
from immortal_mmo.cultivation.breakthrough_catalog import load_breakthrough_catalog
from immortal_mmo.cultivation.models import CultivationState, LifeTechnique, RealmEntry
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.repository import ActiveCultivationSessionExists
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.item.models import ItemStack
from immortal_mmo.player.models import SpiritRoot
from immortal_mmo.player.service import PlayerService

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class RollSequence:
    def __init__(self, *rolls: int) -> None:
        self._rolls = iter(rolls)

    def __call__(self) -> int:
        return next(self._rolls)


def service(
    factory: FakeUnitOfWorkFactory,
    clock: MutableClock,
    *rolls: int,
) -> CultivationService:
    return CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        breakthrough_catalog=load_breakthrough_catalog(ROOT / "breakthrough_rules.json"),
        clock=clock,
        basis_point_roll=RollSequence(*rolls),
        entropy_source=lambda: bytes(range(32)),
    )


async def full_qi_player(
    factory: FakeUnitOfWorkFactory,
    *,
    suffix: int,
    level: int,
    quality: str,
    root_count: int,
    technique_amounts: tuple[int, ...],
    unrefined: int = 777,
) -> tuple[UUID, UUID]:
    login = await PlayerService(factory).login(UUID(int=8_000 + suffix), f"Breaker{suffix}")
    account_id = login.account.account_id
    life_id = login.current_life.life_id
    elements = ("metal", "wood", "water", "fire", "earth")[:root_count]
    factory.store._state.spirit_roots[life_id] = SpiritRoot(
        life_id,
        quality,  # type: ignore[arg-type]
        elements,
        None,
        1,
    )
    for index, amount in enumerate(technique_amounts, start=1):
        technique_id = UUID(int=suffix * 100 + index)
        factory.store._state.life_techniques[technique_id] = LifeTechnique(
            technique_id,
            life_id,
            f"GF_Qi_{index}",
            1,
            "qi",
            "练气",
            amount,
            max(amount, 20_000),
            13,
            "active",
        )
    qi_totals = load_realm_catalog(ROOT / "realm_catalog.json").qi_cumulative_totals()
    baseline = qi_totals[level - 1] if level > 1 else 0
    entry_id = UUID(int=suffix * 1000 + level)
    factory.store._state.realm_entries[entry_id] = RealmEntry(
        entry_id,
        life_id,
        1,
        None,
        max(level - 1, 1),
        level,
        "qi",
        "qi",
        baseline,
        baseline,
        "adjacent",
        None,
        "active",
        None,
    )
    realized = sum(technique_amounts)
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id,
        level,
        unrefined,
        realized,
        None,
        1,
    )
    factory.store._state.cultivation_balances[life_id] = unrefined
    return account_id, life_id


@pytest.mark.asyncio
async def test_guaranteed_foundation_breakthrough_consumes_pill_and_settles_after_restart() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await full_qi_player(
        factory,
        suffix=1,
        level=10,
        quality="triple",
        root_count=3,
        technique_amounts=(11_293,),
    )
    factory.store._state.item_stacks[(life_id, "foundation_pill")] = ItemStack(
        life_id, "foundation_pill", 1, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    idempotency_key = UUID(int=8_001)
    started = await service(factory, clock, 1, 1).start_breakthrough(
        account_id=account_id,
        pill_count=1,
        idempotency_key=idempotency_key,
    )
    replay = await service(factory, clock, 9_999, 9_999).start_breakthrough(
        account_id=account_id,
        pill_count=1,
        idempotency_key=idempotency_key,
    )

    assert replay == started
    assert started.status == "pending"
    assert started.outcome == "success"
    assert factory.store._state.item_stacks[(life_id, "foundation_pill")].quantity == 0

    clock.now += timedelta(minutes=10)
    settled = await service(factory, clock, 9_999, 9_999).settle_breakthrough(
        account_id=account_id,
        session_id=started.session_id,
    )
    snapshot = await service(factory, clock, 1, 1).current_life_snapshot(account_id)

    assert settled.status == "completed"
    assert snapshot.current_level == 14
    assert snapshot.current_progress == 0
    assert snapshot.unrefined_reserve == 777


@pytest.mark.asyncio
async def test_failed_four_root_attempt_can_advance_to_optional_qi_layer_without_loss() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await full_qi_player(
        factory,
        suffix=2,
        level=10,
        quality="quad",
        root_count=4,
        technique_amounts=(11_293,),
    )
    factory.store._state.item_stacks[(life_id, "foundation_pill")] = ItemStack(
        life_id, "foundation_pill", 1, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    started = await service(factory, clock, 10_000, 1).start_breakthrough(
        account_id=account_id,
        pill_count=1,
        idempotency_key=UUID(int=8_002),
    )

    clock.now += timedelta(minutes=10)
    settled = await service(factory, clock, 1, 1).settle_breakthrough(
        account_id=account_id,
        session_id=started.session_id,
    )
    snapshot = await service(factory, clock, 1, 1).current_life_snapshot(account_id)

    assert settled.status == "failed"
    assert settled.outcome == "failure_advance"
    assert snapshot.current_level == 11
    assert snapshot.current_progress == 0
    assert snapshot.realized_total == 11_293
    assert snapshot.unrefined_reserve == 777


@pytest.mark.asyncio
async def test_level_thirteen_failure_applies_fixed_penalty_without_touching_reserve() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await full_qi_player(
        factory,
        suffix=3,
        level=13,
        quality="penta",
        root_count=5,
        technique_amounts=(8_215, 8_215, 8_215, 8_215),
    )
    factory.store._state.item_stacks[(life_id, "foundation_pill")] = ItemStack(
        life_id, "foundation_pill", 10, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    started = await service(factory, clock, 10_000, 10_000).start_breakthrough(
        account_id=account_id,
        pill_count=10,
        idempotency_key=UUID(int=8_003),
    )

    clock.now += timedelta(minutes=10)
    settled = await service(factory, clock, 1, 1).settle_breakthrough(
        account_id=account_id,
        session_id=started.session_id,
    )
    snapshot = await service(factory, clock, 1, 1).current_life_snapshot(account_id)

    assert settled.status == "failed"
    assert settled.outcome == "failure_loss"
    assert snapshot.current_level == 13
    assert snapshot.realized_total == 32_860 - 3_140
    assert snapshot.current_progress == 9_420 - 3_140
    assert snapshot.unrefined_reserve == 777


@pytest.mark.asyncio
async def test_administrative_item_adjustment_is_idempotent() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(UUID(int=8_004), "OperatorTarget")
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    operation_id = UUID(int=8_004)
    cultivation = service(factory, clock, 1, 1)

    first = await cultivation.adjust_item(
        account_id=login.account.account_id,
        item_code="foundation_pill",
        delta_quantity=5,
        idempotency_key=operation_id,
    )
    replay = await cultivation.adjust_item(
        account_id=login.account.account_id,
        item_code="foundation_pill",
        delta_quantity=5,
        idempotency_key=operation_id,
    )

    assert replay == first
    assert first.balance_after == 5
    with pytest.raises(ConflictError, match="idempotency"):
        await cultivation.adjust_item(
            account_id=login.account.account_id,
            item_code="foundation_pill",
            delta_quantity=6,
            idempotency_key=operation_id,
        )


@pytest.mark.asyncio
async def test_breakthrough_item_shortage_is_domain_conflict_and_rolls_back() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await full_qi_player(
        factory,
        suffix=5,
        level=10,
        quality="triple",
        root_count=3,
        technique_amounts=(11_293,),
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    state_before = factory.store._state.cultivation_states[life_id]
    techniques_before = dict(factory.store._state.life_techniques)

    with pytest.raises(DomainError) as raised:
        await service(factory, clock, 1, 1).start_breakthrough(
            account_id=account_id,
            pill_count=1,
            idempotency_key=UUID(int=8_005),
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "item.insufficient_quantity"
    assert factory.store._state.cultivation_states[life_id] == state_before
    assert factory.store._state.life_techniques == techniques_before
    assert factory.store._state.cultivation_sessions == {}
    assert factory.store._state.breakthrough_debits == {}
    assert factory.store._state.item_entries == {}


@pytest.mark.asyncio
async def test_breakthrough_active_session_race_is_domain_conflict_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await full_qi_player(
        factory,
        suffix=6,
        level=10,
        quality="triple",
        root_count=3,
        technique_amounts=(11_293,),
    )
    factory.store._state.item_stacks[(life_id, "foundation_pill")] = ItemStack(
        life_id, "foundation_pill", 1, 1
    )
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    state_before = factory.store._state.cultivation_states[life_id]

    async def raise_race(
        repository: FakeCultivationRepository,
        session,
        techniques,
    ) -> None:
        del repository, techniques
        raise ActiveCultivationSessionExists(session.life_id)

    monkeypatch.setattr(FakeCultivationRepository, "start_session", raise_race)

    with pytest.raises(DomainError) as raised:
        await service(factory, clock, 1, 1).start_breakthrough(
            account_id=account_id,
            pill_count=1,
            idempotency_key=UUID(int=8_006),
        )

    assert raised.value.status_code == 409
    assert raised.value.code == "cultivation.breakthrough_conflict"
    assert factory.store._state.cultivation_states[life_id] == state_before
    assert factory.store._state.cultivation_sessions == {}
    assert factory.store._state.breakthrough_debits == {}
    assert factory.store._state.item_stacks[(life_id, "foundation_pill")].quantity == 1
    assert factory.store._state.item_entries == {}
