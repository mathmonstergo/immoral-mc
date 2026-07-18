from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from tests.support.fakes import (
    FakeCultivationRepository,
    FakeStore,
    FakeUnitOfWorkFactory,
)

from immortal_mmo.core.errors import DomainError
from immortal_mmo.cultivation.area_catalog import load_area_catalog
from immortal_mmo.cultivation.models import CultivationSession, LifeTechnique
from immortal_mmo.cultivation.realm_catalog import load_realm_catalog
from immortal_mmo.cultivation.repository import ActiveCultivationSessionExists
from immortal_mmo.cultivation.service import CultivationService
from immortal_mmo.player.service import PlayerService

ROOT = Path(__file__).resolve().parents[2] / "src/immortal_mmo/cultivation"


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def cultivation_service(
    factory: FakeUnitOfWorkFactory,
    *,
    clock: MutableClock | None = None,
) -> CultivationService:
    return CultivationService(
        factory,
        load_realm_catalog(ROOT / "realm_catalog.json"),
        area_catalog=load_area_catalog(ROOT / "areas.json"),
        clock=clock,
    )


async def logged_in_player(
    factory: FakeUnitOfWorkFactory,
    *,
    suffix: int,
) -> tuple[UUID, UUID]:
    login = await PlayerService(factory).login(UUID(int=20_000 + suffix), f"Errors{suffix}")
    return login.account.account_id, login.current_life.life_id


def add_technique(
    factory: FakeUnitOfWorkFactory,
    *,
    life_id: UUID,
    technique_id: UUID,
    group_code: str = "qi",
    major_realm: str = "练气",
    invested_amount: int = 0,
    max_investment: int = 100,
    status: str = "active",
) -> None:
    factory.store._state.life_techniques[technique_id] = LifeTechnique(
        life_technique_id=technique_id,
        life_id=life_id,
        technique_id=f"GF_Error_{technique_id.int}",
        definition_version=1,
        group_code=group_code,
        major_realm=major_realm,
        invested_amount=invested_amount,
        max_investment=max_investment,
        current_layer=0 if invested_amount == 0 else 1,
        status=status,
    )


async def assert_domain_error(
    awaitable: object,
    *,
    code: str,
    status_code: int,
) -> None:
    with pytest.raises(DomainError) as raised:
        await awaitable  # type: ignore[misc]
    assert raised.value.code == code
    assert raised.value.status_code == status_code


@pytest.mark.asyncio
async def test_start_seclusion_rejects_duplicate_technique_ids_as_rule_violation() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=1)
    technique_id = UUID(int=20_101)
    add_technique(factory, life_id=life_id, technique_id=technique_id)

    await assert_domain_error(
        cultivation_service(factory).start_seclusion(
            account_id=account_id,
            area_id="neutral_training_ground",
            technique_ids=(technique_id, technique_id),
            idempotency_key=UUID(int=20_102),
        ),
        code="cultivation.seclusion_rule_violation",
        status_code=409,
    )


@pytest.mark.asyncio
async def test_start_seclusion_rejects_unknown_area_as_rule_violation() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=2)
    technique_id = UUID(int=20_201)
    add_technique(factory, life_id=life_id, technique_id=technique_id)

    await assert_domain_error(
        cultivation_service(factory).start_seclusion(
            account_id=account_id,
            area_id="unknown-area",
            technique_ids=(technique_id,),
            idempotency_key=UUID(int=20_202),
        ),
        code="cultivation.seclusion_rule_violation",
        status_code=409,
    )


@pytest.mark.asyncio
async def test_start_seclusion_rejects_changed_idempotent_request_as_conflict() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=3)
    technique_ids = (UUID(int=20_301), UUID(int=20_302))
    for technique_id in technique_ids:
        add_technique(factory, life_id=life_id, technique_id=technique_id)
    service = cultivation_service(factory)
    idempotency_key = UUID(int=20_303)
    await service.start_seclusion(
        account_id=account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_ids[0],),
        idempotency_key=idempotency_key,
    )

    await assert_domain_error(
        service.start_seclusion(
            account_id=account_id,
            area_id="accelerated_cave",
            technique_ids=(technique_ids[1],),
            idempotency_key=idempotency_key,
        ),
        code="cultivation.seclusion_conflict",
        status_code=409,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unknown", "wrong_life", "mixed", "abandoned", "full"])
async def test_start_seclusion_rejects_ineligible_selection_as_rule_violation(
    case: str,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=10)
    other_account_id, other_life_id = await logged_in_player(factory, suffix=11)
    del other_account_id
    first_id = UUID(int=20_401)
    second_id = UUID(int=20_402)
    selected_ids = (first_id,)

    if case == "unknown":
        pass
    elif case == "wrong_life":
        add_technique(factory, life_id=other_life_id, technique_id=first_id)
    elif case == "mixed":
        add_technique(factory, life_id=life_id, technique_id=first_id)
        add_technique(
            factory,
            life_id=life_id,
            technique_id=second_id,
            group_code="level:14",
            major_realm="筑基",
        )
        selected_ids = (first_id, second_id)
    elif case == "abandoned":
        add_technique(
            factory,
            life_id=life_id,
            technique_id=first_id,
            status="abandoned",
        )
    else:
        add_technique(
            factory,
            life_id=life_id,
            technique_id=first_id,
            invested_amount=100,
            max_investment=100,
        )

    await assert_domain_error(
        cultivation_service(factory).start_seclusion(
            account_id=account_id,
            area_id="neutral_training_ground",
            technique_ids=selected_ids,
            idempotency_key=UUID(int=20_403),
        ),
        code="cultivation.seclusion_rule_violation",
        status_code=409,
    )


@pytest.mark.asyncio
async def test_start_seclusion_rejects_existing_open_session_as_conflict() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=5)
    technique_id = UUID(int=20_501)
    add_technique(factory, life_id=life_id, technique_id=technique_id)
    service = cultivation_service(factory)
    await service.start_seclusion(
        account_id=account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_id,),
        idempotency_key=UUID(int=20_502),
    )

    await assert_domain_error(
        service.start_seclusion(
            account_id=account_id,
            area_id="neutral_training_ground",
            technique_ids=(technique_id,),
            idempotency_key=UUID(int=20_503),
        ),
        code="cultivation.seclusion_conflict",
        status_code=409,
    )
    assert len(factory.store._state.cultivation_sessions) == 1


@pytest.mark.asyncio
async def test_start_seclusion_translates_repository_race_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=6)
    technique_id = UUID(int=20_601)
    add_technique(factory, life_id=life_id, technique_id=technique_id)

    async def raise_race_conflict(
        repository: FakeCultivationRepository,
        session: CultivationSession,
        techniques: tuple[object, ...],
    ) -> None:
        del repository, techniques
        raise ActiveCultivationSessionExists(session.life_id)

    monkeypatch.setattr(FakeCultivationRepository, "start_session", raise_race_conflict)

    await assert_domain_error(
        cultivation_service(factory).start_seclusion(
            account_id=account_id,
            area_id="neutral_training_ground",
            technique_ids=(technique_id,),
            idempotency_key=UUID(int=20_602),
        ),
        code="cultivation.seclusion_conflict",
        status_code=409,
    )


def stored_session(
    *,
    life_id: UUID,
    session_id: UUID,
    session_kind: str,
    now: datetime,
) -> CultivationSession:
    return CultivationSession(
        session_id=session_id,
        life_id=life_id,
        session_kind=session_kind,
        status="pending",
        idempotency_key=UUID(int=session_id.int + 1),
        request_fingerprint="0" * 64,
        area_id=None,
        content_version="test:v1",
        source_level=10,
        target_level=14,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["status", "settle"])
@pytest.mark.parametrize("case", ["unknown", "wrong_life", "wrong_kind"])
async def test_seclusion_reads_reject_non_ordinary_current_life_session_as_not_found(
    operation: str,
    case: str,
) -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=7)
    _, other_life_id = await logged_in_player(factory, suffix=8)
    now = datetime(2026, 7, 16, 8, tzinfo=UTC)
    session_id = UUID(int=20_701)
    if case != "unknown":
        factory.store._state.cultivation_sessions[session_id] = stored_session(
            life_id=other_life_id if case == "wrong_life" else life_id,
            session_id=session_id,
            session_kind="ordinary" if case == "wrong_life" else "breakthrough",
            now=now,
        )
    service = cultivation_service(factory, clock=MutableClock(now))
    call = (
        service.seclusion_status(account_id=account_id, session_id=session_id)
        if operation == "status"
        else service.settle_seclusion(account_id=account_id, session_id=session_id)
    )

    await assert_domain_error(
        call,
        code="cultivation.seclusion_not_found",
        status_code=404,
    )


@pytest.mark.asyncio
async def test_settle_seclusion_rejects_too_early_settlement_as_conflict() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id, life_id = await logged_in_player(factory, suffix=9)
    technique_id = UUID(int=20_901)
    add_technique(factory, life_id=life_id, technique_id=technique_id)
    clock = MutableClock(datetime(2026, 7, 16, 8, tzinfo=UTC))
    service = cultivation_service(factory, clock=clock)
    started = await service.start_seclusion(
        account_id=account_id,
        area_id="neutral_training_ground",
        technique_ids=(technique_id,),
        idempotency_key=UUID(int=20_902),
    )
    clock.now += timedelta(seconds=9)

    await assert_domain_error(
        service.settle_seclusion(account_id=account_id, session_id=started.session_id),
        code="cultivation.seclusion_conflict",
        status_code=409,
    )
