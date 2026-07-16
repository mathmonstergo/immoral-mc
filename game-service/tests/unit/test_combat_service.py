from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from tests.support.fakes import (
    FakeCultivationRepository,
    FakeStore,
    FakeUnitOfWorkFactory,
)

from immortal_mmo.combat.catalog import (
    CombatRewardCatalog,
    LevelRewardCurve,
    MobRewardDefinition,
    RewardProfile,
)
from immortal_mmo.combat.schemas import CombatKillBatchRequest, CombatKillEventRequest
from immortal_mmo.combat.service import CombatIdempotencyConflictError, CombatRewardService
from immortal_mmo.cultivation.models import CultivationState
from immortal_mmo.player.service import PlayerService

KILLER_ID = UUID("33333333-3333-4333-8333-333333333333")


def catalog() -> CombatRewardCatalog:
    return CombatRewardCatalog(
        schema_version=1,
        curves=(
            LevelRewardCurve(
                "linear-low",
                Decimal("1.000"),
                Decimal("100.000"),
                2,
            ),
        ),
        profiles=(RewardProfile("ordinary-wolf", 10, "linear-low"),),
        mobs=(MobRewardDefinition("AzureWolf", "ordinary-wolf", "compact"),),
    )


def catalog_with_level_one_only() -> CombatRewardCatalog:
    return CombatRewardCatalog(
        schema_version=1,
        curves=(
            LevelRewardCurve(
                "linear-low",
                Decimal("1.000"),
                Decimal("1.000"),
                2,
            ),
        ),
        profiles=(RewardProfile("ordinary-wolf", 10, "linear-low"),),
        mobs=(MobRewardDefinition("AzureWolf", "ordinary-wolf", "compact"),),
    )


def event(
    *,
    event_id: UUID | None = None,
    source_life_id: UUID | None = None,
    mob_internal_name: str = "AzureWolf",
    technique_id: str = "venom_mist",
) -> CombatKillEventRequest:
    return CombatKillEventRequest.model_validate(
        {
            "contract_version": 1,
            "event_id": str(event_id or uuid4()),
            "server_id": "main-1",
            "entity_uuid": str(uuid4()),
            "mob_internal_name": mob_internal_name,
            "mob_level": "2.000",
            "killer_uuid": str(KILLER_ID),
            "source_life_id": str(source_life_id) if source_life_id else None,
            "attribution_kind": "damage_over_time",
            "technique_id": technique_id,
            "cast_id": str(uuid4()),
            "world": "minecraft:overworld",
            "x": 12.5,
            "y": 64.0,
            "z": -8.25,
            "occurred_at": "2026-07-15T12:00:00Z",
        }
    )


async def logged_in_factory() -> tuple[FakeUnitOfWorkFactory, UUID]:
    factory = FakeUnitOfWorkFactory(FakeStore())
    login = await PlayerService(factory).login(KILLER_ID, "Combatant")
    return factory, login.current_life.life_id


@pytest.mark.asyncio
async def test_reward_service_credits_current_life_once_and_replays_duplicate() -> None:
    factory, life_id = await logged_in_factory()
    service = CombatRewardService(factory, catalog())
    request_event = event(source_life_id=life_id)
    batch = CombatKillBatchRequest(events=[request_event])

    first = await service.process_batch(batch)
    replay = await service.process_batch(batch)

    assert first.results[0].outcome == "accepted"
    assert first.results[0].configured_reward_amount == 12
    assert first.results[0].credited_cultivation_amount == 12
    assert first.results[0].unrefined_balance == 12
    assert replay.results[0].outcome == "duplicate"
    assert replay.results[0].configured_reward_amount == 12
    assert replay.results[0].credited_cultivation_amount == 12
    async with factory() as uow:
        assert await uow.combat.get_mob_counter(life_id, "AzureWolf") == 1
        assert await uow.cultivation.get_unrefined_balance(life_id) == 12
        stored = await uow.combat.get_event(request_event.event_id)
        assert stored is not None
        assert stored.killer_minecraft_uuid == KILLER_ID
        assert stored.source_life_id == life_id
        assert stored.attribution_kind == "damage_over_time"
        assert stored.technique_id == "venom_mist"
        assert stored.cast_id == request_event.cast_id


@pytest.mark.asyncio
async def test_reward_service_replays_stored_result_before_current_catalog_validation() -> None:
    factory, life_id = await logged_in_factory()
    request_event = event(source_life_id=life_id)
    batch = CombatKillBatchRequest(events=[request_event])
    accepted = await CombatRewardService(factory, catalog()).process_batch(batch)

    replay = await CombatRewardService(
        factory,
        catalog_with_level_one_only(),
    ).process_batch(batch)

    assert accepted.results[0].outcome == "accepted"
    assert replay.results[0].outcome == "duplicate"
    assert replay.results[0].configured_reward_amount == 12
    assert replay.results[0].credited_cultivation_amount == 12
    assert replay.results[0].unrefined_balance == 12


@pytest.mark.asyncio
async def test_reward_service_rejects_same_event_id_with_changed_identity() -> None:
    factory, life_id = await logged_in_factory()
    service = CombatRewardService(factory, catalog())
    event_id = uuid4()
    original = event(event_id=event_id, source_life_id=life_id)
    changed = event(
        event_id=event_id,
        source_life_id=life_id,
        technique_id="different_technique",
    )
    await service.process_batch(CombatKillBatchRequest(events=[original]))

    with pytest.raises(CombatIdempotencyConflictError):
        await service.process_batch(CombatKillBatchRequest(events=[changed]))


@pytest.mark.asyncio
async def test_unknown_mob_is_terminal_without_account_or_reward_lookup() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    service = CombatRewardService(factory, catalog())
    request_event = event(mob_internal_name="UnknownMob")

    result = await service.process_batch(CombatKillBatchRequest(events=[request_event]))

    assert result.results[0].outcome == "not_rewardable"
    assert result.results[0].configured_reward_amount is None
    assert result.results[0].credited_cultivation_amount is None
    async with factory() as uow:
        stored = await uow.combat.get_event(request_event.event_id)
        assert stored is not None
        assert stored.outcome == "not_rewardable"


@pytest.mark.asyncio
async def test_known_mob_without_account_is_terminal() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    service = CombatRewardService(factory, catalog())

    result = await service.process_batch(CombatKillBatchRequest(events=[event()]))

    assert result.results[0].outcome == "account_not_found"


@pytest.mark.asyncio
async def test_known_mob_without_current_life_is_terminal() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    async with factory() as uow:
        await uow.players.upsert_account(KILLER_ID, "Combatant")
        await uow.commit()

    result = await CombatRewardService(factory, catalog()).process_batch(
        CombatKillBatchRequest(events=[event()])
    )

    assert result.results[0].outcome == "current_life_unavailable"


@pytest.mark.asyncio
async def test_stale_source_life_cannot_credit_current_life() -> None:
    factory, current_life_id = await logged_in_factory()
    service = CombatRewardService(factory, catalog())
    request_event = event(source_life_id=uuid4())

    result = await service.process_batch(CombatKillBatchRequest(events=[request_event]))

    assert result.results[0].outcome == "current_life_unavailable"
    async with factory() as uow:
        assert await uow.cultivation.get_unrefined_balance(current_life_id) == 0


@pytest.mark.asyncio
async def test_full_reserve_kill_is_accepted_with_zero_credit() -> None:
    factory, life_id = await logged_in_factory()
    factory.store._state.cultivation_balances[life_id] = 100
    factory.store._state.cultivation_states[life_id] = CultivationState(
        life_id=life_id,
        current_level=1,
        unrefined_cultivation=100,
        realized_cultivation=0,
        active_session_id=None,
        revision=2,
    )
    result = await CombatRewardService(factory, catalog()).process_batch(
        CombatKillBatchRequest(events=[event(source_life_id=life_id)])
    )

    assert result.results[0].outcome == "accepted"
    assert result.results[0].configured_reward_amount == 12
    assert result.results[0].credited_cultivation_amount == 0
    assert result.results[0].unrefined_balance == 100


@pytest.mark.asyncio
async def test_reward_service_rolls_back_all_combat_writes_when_credit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, life_id = await logged_in_factory()
    request_event = event(source_life_id=life_id)

    async def fail_credit(
        self: FakeCultivationRepository,
        *,
        life_id: UUID,
        kill_event_id: UUID,
        amount: int,
        cap: int,
        occurred_at: object,
    ) -> None:
        del self, life_id, kill_event_id, amount, cap, occurred_at
        raise RuntimeError("simulated cultivation write failure")

    monkeypatch.setattr(
        FakeCultivationRepository,
        "credit_combat_reward",
        fail_credit,
    )

    with pytest.raises(RuntimeError, match="simulated cultivation write failure"):
        await CombatRewardService(factory, catalog()).process_batch(
            CombatKillBatchRequest(events=[request_event])
        )

    async with factory() as uow:
        assert await uow.combat.get_event(request_event.event_id) is None
        assert await uow.combat.get_mob_counter(life_id, "AzureWolf") == 0
        assert await uow.cultivation.get_unrefined_balance(life_id) == 0
