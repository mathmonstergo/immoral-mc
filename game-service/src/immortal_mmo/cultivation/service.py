import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.cultivation.allocation import allocate_equal
from immortal_mmo.cultivation.area_catalog import AreaCatalog, load_area_catalog
from immortal_mmo.cultivation.models import (
    CultivationSession,
    RealmEntry,
    SessionTechnique,
    TechniqueInvestmentChange,
)
from immortal_mmo.cultivation.progression import group_for_level, project_progress
from immortal_mmo.cultivation.realm_catalog import RealmCatalog
from immortal_mmo.cultivation.schemas import (
    CultivationSnapshotResponse,
    SeclusionSnapshotResponse,
)
from immortal_mmo.cultivation.seclusion import (
    cumulative_time_budget,
    maximum_convertible_reserve,
)
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError

FULL_MASTERY_SECONDS = {"练气": 36_000, "筑基": 72_000, "结丹": 180_000, "元婴": 360_000}


class CultivationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        realm_catalog: RealmCatalog,
        *,
        area_catalog: AreaCatalog | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._realm_catalog = realm_catalog
        self._area_catalog = area_catalog or load_area_catalog(
            Path(__file__).resolve().parent / "areas.json"
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    async def current_life_snapshot(self, account_id: UUID) -> CultivationSnapshotResponse:
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=False)
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            chain = await uow.cultivation.get_active_realm_chain(life.life_id, for_update=False)
            snapshot = project_progress(
                catalog=self._realm_catalog,
                current_level=state.current_level,
                group_investments=group_investments,
                active_entry=chain[-1] if chain else None,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            await uow.commit()
        return CultivationSnapshotResponse(**asdict(snapshot))

    async def start_seclusion(
        self,
        *,
        account_id: UUID,
        area_id: str,
        technique_ids: tuple[UUID, ...],
        idempotency_key: UUID,
    ) -> SeclusionSnapshotResponse:
        if not 1 <= len(technique_ids) <= 5 or len(set(technique_ids)) != len(technique_ids):
            raise ValueError("Seclusion requires one to five unique techniques")
        area = self._area_catalog.area(area_id)
        now = self._clock()
        request_fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "area_id": area_id,
                    "technique_ids": sorted(str(value) for value in technique_ids),
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            existing = await uow.cultivation.get_session_by_idempotency(
                life.life_id, idempotency_key
            )
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise ValueError("Seclusion idempotency key was reused")
                await uow.rollback()
                return _seclusion_snapshot(existing)
            await uow.cultivation.get_or_create_state(life.life_id, for_update=True)
            techniques = await uow.cultivation.get_techniques(
                life.life_id, technique_ids, for_update=True
            )
            if len(techniques) != len(technique_ids):
                raise ValueError("Unknown selected technique")
            if len({item.major_realm for item in techniques}) != 1:
                raise ValueError("Selected techniques must share the same major realm")
            if any(
                item.status != "active" or item.invested_amount >= item.max_investment
                for item in techniques
            ):
                raise ValueError("Selected technique is not eligible for seclusion")
            full_seconds = FULL_MASTERY_SECONDS[techniques[0].major_realm]
            session_id = uuid4()
            session = CultivationSession(
                session_id=session_id,
                life_id=life.life_id,
                session_kind="ordinary",
                status="active",
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                area_id=area.area_id,
                content_version=self._area_catalog.revision,
                source_level=(
                    await uow.cultivation.get_or_create_state(life.life_id, for_update=False)
                ).current_level,
                target_level=None,
                frozen_snapshot={
                    "area_version": area.version,
                    "speed_basis_points": area.speed_basis_points,
                    "yield_basis_points": area.yield_basis_points,
                },
                cumulative_elapsed_seconds=0,
                cumulative_generated=0,
                cumulative_reserve_consumed=0,
                cumulative_retained=0,
                started_at=now,
                completes_at=now + timedelta(seconds=full_seconds),
                settled_at=None,
                revision=1,
            )
            selections = tuple(
                SessionTechnique(
                    session_id=session_id,
                    life_id=life.life_id,
                    life_technique_id=item.life_technique_id,
                    definition_version=item.definition_version,
                    group_code=item.group_code,
                    major_realm=item.major_realm,
                    frozen_capacity=item.max_investment,
                    frozen_invested=item.invested_amount,
                    frozen_full_mastery_seconds=full_seconds,
                )
                for item in techniques
            )
            await uow.cultivation.start_session(session, selections)
            await uow.commit()
        return _seclusion_snapshot(session)

    async def settle_seclusion(
        self, *, account_id: UUID, session_id: UUID
    ) -> SeclusionSnapshotResponse:
        now = self._clock()
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=True)
            if session is None or session.life_id != life.life_id:
                raise ValueError("Unknown seclusion session")
            if session.status not in {"active", "pending"}:
                await uow.rollback()
                return _seclusion_snapshot(session)
            selections = await uow.cultivation.get_session_techniques(session_id)
            techniques = await uow.cultivation.get_techniques(
                life.life_id,
                tuple(item.life_technique_id for item in selections),
                for_update=True,
            )
            elapsed = max(int((now - session.started_at).total_seconds()), 0)
            if elapsed <= 0:
                raise ValueError("Seclusion has no elapsed time to settle")
            speed = int(session.frozen_snapshot["speed_basis_points"])
            yield_points = int(session.frozen_snapshot["yield_basis_points"])
            capacities = [item.frozen_capacity for item in selections]
            cumulative_generated = cumulative_time_budget(
                elapsed,
                speed,
                capacities,
                selections[0].frozen_full_mastery_seconds,
            )
            unused_time_budget = max(cumulative_generated - session.cumulative_generated, 0)
            remaining = {
                item.life_technique_id: item.max_investment - item.invested_amount
                for item in techniques
            }
            effective_cap = min(unused_time_budget, sum(remaining.values()))
            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=True)
            reserve_consumed = min(
                state.unrefined_cultivation,
                maximum_convertible_reserve(effective_cap, yield_points),
            )
            retained = reserve_consumed * yield_points // 10_000
            allocations = allocate_equal(retained, remaining)
            operation_id = uuid4()
            if retained > 0:
                await uow.cultivation.apply_technique_investments(
                    life_id=life.life_id,
                    operation_id=operation_id,
                    session_id=session_id,
                    changes=tuple(
                        TechniqueInvestmentChange(technique_id, amount, "seclusion_realization")
                        for technique_id, amount in allocations.items()
                        if amount > 0
                    ),
                    occurred_at=now,
                )
                await uow.cultivation.consume_unrefined(
                    life_id=life.life_id,
                    session_id=session_id,
                    operation_id=operation_id,
                    amount=reserve_consumed,
                    occurred_at=now,
                )
            active_chain = await uow.cultivation.get_active_realm_chain(
                life.life_id, for_update=True
            )
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            current_level = state.current_level
            parent_entry = active_chain[-1] if active_chain else None
            generation = await uow.cultivation.get_latest_realm_generation(life.life_id)
            qi_totals = self._realm_catalog.qi_cumulative_totals()
            while current_level < 10 and group_investments.get("qi", 0) >= qi_totals[current_level]:
                generation += 1
                source_floor = qi_totals[current_level]
                realm_entry = RealmEntry(
                    realm_entry_id=uuid4(),
                    life_id=life.life_id,
                    generation=generation,
                    parent_entry_id=(
                        None if parent_entry is None else parent_entry.realm_entry_id
                    ),
                    source_level=current_level,
                    target_level=current_level + 1,
                    source_group="qi",
                    target_group="qi",
                    source_floor=source_floor,
                    target_baseline=source_floor,
                    transition_kind="adjacent",
                    transition_session_id=session_id,
                    status="active",
                    invalidated_at=None,
                )
                state = await uow.cultivation.append_realm_entry(realm_entry)
                parent_entry = realm_entry
                current_level = state.current_level
            progress = project_progress(
                catalog=self._realm_catalog,
                current_level=current_level,
                group_investments=group_investments,
                active_entry=parent_entry,
                unrefined_reserve=state.unrefined_cultivation - reserve_consumed,
                revision=state.revision,
            )
            selected_mastered = retained == sum(remaining.values()) and bool(remaining)
            explicit_barrier_full = progress.progress_full and (
                current_level >= 10 or group_for_level(current_level) != "qi"
            )
            terminal = selected_mastered or explicit_barrier_full
            updated = await uow.cultivation.update_session_settlement(
                session_id=session_id,
                cumulative_elapsed_seconds=elapsed,
                cumulative_generated=cumulative_generated,
                cumulative_reserve_consumed=(
                    session.cumulative_reserve_consumed + reserve_consumed
                ),
                cumulative_retained=session.cumulative_retained + retained,
                status="completed" if terminal else "active",
                settled_at=now if terminal else None,
            )
            await uow.commit()
        return _seclusion_snapshot(updated)

    async def seclusion_status(
        self, *, account_id: UUID, session_id: UUID
    ) -> SeclusionSnapshotResponse:
        async with self._uow_factory() as uow:
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            session = await uow.cultivation.get_session(session_id, for_update=False)
            if session is None or session.life_id != life.life_id:
                raise ValueError("Unknown seclusion session")
            await uow.rollback()
        return _seclusion_snapshot(session)


def _seclusion_snapshot(session: CultivationSession) -> SeclusionSnapshotResponse:
    return SeclusionSnapshotResponse(
        session_id=session.session_id,
        status=session.status,
        started_at=session.started_at,
        completes_at=session.completes_at,
        cumulative_generated=session.cumulative_generated,
        cumulative_reserve_consumed=session.cumulative_reserve_consumed,
        cumulative_retained=session.cumulative_retained,
    )
