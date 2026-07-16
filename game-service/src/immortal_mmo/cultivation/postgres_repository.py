from collections.abc import Collection
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.combat.catalog import MAX_REWARD_AMOUNT
from immortal_mmo.cultivation.db_models import (
    CultivationResourceEntryRow,
    CultivationSessionRow,
    LifeCultivationStateRow,
    LifeRealmEntryRow,
    LifeTechniqueRow,
    TechniqueInvestmentEntryRow,
)
from immortal_mmo.cultivation.models import (
    CombatCultivationCredit,
    CultivationSession,
    CultivationState,
    LifeTechnique,
    RealmEntry,
    TechniqueInvestmentChange,
)


class ActiveCultivationSessionExists(RuntimeError):
    """Raised when a life already owns an open cultivation mutation session."""


class PostgresCultivationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_state(self, life_id: UUID, *, for_update: bool) -> CultivationState:
        await self._session.execute(
            insert(LifeCultivationStateRow)
            .values(life_id=life_id)
            .on_conflict_do_nothing(index_elements=[LifeCultivationStateRow.life_id])
        )
        statement = select(LifeCultivationStateRow).where(
            LifeCultivationStateRow.life_id == life_id
        )
        if for_update:
            statement = statement.with_for_update(of=LifeCultivationStateRow)
        row = await self._session.scalar(statement)
        if row is None:
            raise RuntimeError("Cultivation state disappeared after initialization")
        return _state(row)

    async def get_techniques(
        self,
        life_id: UUID,
        technique_ids: Collection[UUID] = (),
        *,
        for_update: bool,
    ) -> tuple[LifeTechnique, ...]:
        statement = (
            select(LifeTechniqueRow)
            .where(LifeTechniqueRow.life_id == life_id)
            .order_by(LifeTechniqueRow.life_technique_id)
        )
        if technique_ids:
            statement = statement.where(
                LifeTechniqueRow.life_technique_id.in_(tuple(technique_ids))
            )
        if for_update:
            statement = statement.with_for_update(of=LifeTechniqueRow)
        rows = (await self._session.scalars(statement)).all()
        return tuple(_technique(row) for row in rows)

    async def get_active_realm_chain(
        self, life_id: UUID, *, for_update: bool
    ) -> tuple[RealmEntry, ...]:
        statement = (
            select(LifeRealmEntryRow)
            .where(
                LifeRealmEntryRow.life_id == life_id,
                LifeRealmEntryRow.status == "active",
            )
            .order_by(LifeRealmEntryRow.generation)
        )
        if for_update:
            statement = statement.with_for_update(of=LifeRealmEntryRow)
        rows = (await self._session.scalars(statement)).all()
        return tuple(_realm_entry(row) for row in rows)

    async def get_group_investments(self, life_id: UUID) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(
                    LifeTechniqueRow.group_code,
                    func.coalesce(func.sum(LifeTechniqueRow.invested_amount), 0),
                )
                .where(LifeTechniqueRow.life_id == life_id)
                .group_by(LifeTechniqueRow.group_code)
            )
        ).all()
        return {group_code: int(total) for group_code, total in rows}

    async def insert_session(self, session: CultivationSession) -> None:
        row = CultivationSessionRow(
            session_id=session.session_id,
            life_id=session.life_id,
            session_kind=session.session_kind,
            status=session.status,
            idempotency_key=session.idempotency_key,
            request_fingerprint=session.request_fingerprint,
            area_id=session.area_id,
            content_version=session.content_version,
            source_level=session.source_level,
            target_level=session.target_level,
            frozen_snapshot=session.frozen_snapshot,
            cumulative_elapsed_seconds=session.cumulative_elapsed_seconds,
            cumulative_generated=session.cumulative_generated,
            cumulative_reserve_consumed=session.cumulative_reserve_consumed,
            cumulative_retained=session.cumulative_retained,
            started_at=session.started_at,
            completes_at=session.completes_at,
            settled_at=session.settled_at,
            revision=session.revision,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError as error:
            constraint_name = getattr(error.orig.__cause__, "constraint_name", None)
            if constraint_name == "ux_cultivation_one_open_session":
                raise ActiveCultivationSessionExists(session.life_id) from error
            raise

    async def apply_technique_investments(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        session_id: UUID | None,
        changes: tuple[TechniqueInvestmentChange, ...],
        occurred_at: datetime,
    ) -> CultivationState:
        if not changes:
            raise ValueError("Technique investment changes must not be empty")
        technique_ids = tuple(change.life_technique_id for change in changes)
        if len(set(technique_ids)) != len(technique_ids):
            raise ValueError("Technique investment changes must be unique")
        state = await self.get_or_create_state(life_id, for_update=True)
        techniques = await self.get_techniques(life_id, technique_ids, for_update=True)
        if len(techniques) != len(changes):
            raise KeyError("Unknown life technique")
        changes_by_id = {change.life_technique_id: change for change in changes}
        planned: list[tuple[LifeTechnique, TechniqueInvestmentChange, int]] = []
        for technique in techniques:
            change = changes_by_id[technique.life_technique_id]
            if change.delta_amount == 0:
                raise ValueError("Technique investment delta must not be zero")
            balance_after = technique.invested_amount + change.delta_amount
            if not 0 <= balance_after <= technique.max_investment:
                raise ValueError("Technique investment exceeds its bounds")
            planned.append((technique, change, balance_after))
        total_delta = sum(change.delta_amount for _, change, _ in planned)
        realized_after = state.realized_cultivation + total_delta
        if realized_after < 0:
            raise ValueError("Realized cultivation cannot become negative")

        for technique, change, balance_after in planned:
            await self._session.execute(
                update(LifeTechniqueRow)
                .where(
                    LifeTechniqueRow.life_id == life_id,
                    LifeTechniqueRow.life_technique_id == technique.life_technique_id,
                )
                .values(invested_amount=balance_after, updated_at=func.now())
            )
            self._session.add(
                TechniqueInvestmentEntryRow(
                    entry_id=uuid4(),
                    life_id=life_id,
                    life_technique_id=technique.life_technique_id,
                    session_id=session_id,
                    operation_id=operation_id,
                    entry_type=change.entry_type,
                    delta_amount=change.delta_amount,
                    balance_after=balance_after,
                    created_at=occurred_at,
                )
            )
        updated = (
            await self._session.execute(
                update(LifeCultivationStateRow)
                .where(LifeCultivationStateRow.life_id == life_id)
                .values(
                    realized_cultivation=realized_after,
                    revision=LifeCultivationStateRow.revision + 1,
                    updated_at=func.now(),
                )
                .returning(LifeCultivationStateRow)
            )
        ).scalar_one()
        if total_delta != 0:
            self._session.add(
                CultivationResourceEntryRow(
                    entry_id=uuid4(),
                    life_id=life_id,
                    resource_code="realized_cultivation",
                    entry_type=_resource_entry_type(changes),
                    delta_amount=total_delta,
                    balance_after=realized_after,
                    kill_event_id=None,
                    session_id=session_id,
                    operation_id=operation_id,
                    created_at=occurred_at,
                )
            )
        await self._session.flush()
        return _state(updated)

    async def get_combat_credit(
        self,
        kill_event_id: UUID,
        life_id: UUID,
    ) -> CombatCultivationCredit | None:
        entry = await self._session.scalar(
            select(CultivationResourceEntryRow).where(
                CultivationResourceEntryRow.kill_event_id == kill_event_id,
                CultivationResourceEntryRow.life_id == life_id,
                CultivationResourceEntryRow.entry_type == "combat_reward",
            )
        )
        if entry is None:
            return None
        state = await self._session.get(LifeCultivationStateRow, life_id)
        if state is None:
            raise RuntimeError("Combat reward entry has no cultivation state")
        return CombatCultivationCredit(
            entry_id=entry.entry_id,
            life_id=life_id,
            kill_event_id=kill_event_id,
            amount=entry.delta_amount,
            balance_after=entry.balance_after,
            revision=state.revision,
        )

    async def credit_combat_reward(
        self,
        *,
        life_id: UUID,
        kill_event_id: UUID,
        amount: int,
        cap: int,
        occurred_at: datetime,
    ) -> CombatCultivationCredit:
        if amount <= 0 or amount > MAX_REWARD_AMOUNT:
            raise ValueError("Combat cultivation reward amount is invalid")
        await self._session.execute(
            insert(LifeCultivationStateRow)
            .values(life_id=life_id)
            .on_conflict_do_nothing(index_elements=[LifeCultivationStateRow.life_id])
        )
        state = await self._session.scalar(
            select(LifeCultivationStateRow)
            .where(LifeCultivationStateRow.life_id == life_id)
            .with_for_update(of=LifeCultivationStateRow)
        )
        if state is None:
            raise RuntimeError("Cultivation state disappeared before reward credit")
        if cap <= 0:
            raise ValueError("Combat cultivation reserve cap must be positive")
        available = max(cap - state.unrefined_cultivation, 0)
        credited_amount = min(amount, available)
        balance_after = state.unrefined_cultivation + credited_amount
        updated = (
            await self._session.execute(
                update(LifeCultivationStateRow)
                .where(LifeCultivationStateRow.life_id == life_id)
                .values(
                    unrefined_cultivation=balance_after,
                    revision=LifeCultivationStateRow.revision + 1,
                    updated_at=func.now(),
                )
                .returning(
                    LifeCultivationStateRow.unrefined_cultivation,
                    LifeCultivationStateRow.revision,
                )
            )
        ).one()
        entry_id = None
        if credited_amount > 0:
            entry_id = uuid4()
            self._session.add(
                CultivationResourceEntryRow(
                    entry_id=entry_id,
                    life_id=life_id,
                    resource_code="unrefined_cultivation",
                    entry_type="combat_reward",
                    delta_amount=credited_amount,
                    balance_after=updated.unrefined_cultivation,
                    kill_event_id=kill_event_id,
                    created_at=occurred_at,
                )
            )
        await self._session.flush()
        return CombatCultivationCredit(
            entry_id=entry_id,
            life_id=life_id,
            kill_event_id=kill_event_id,
            amount=credited_amount,
            balance_after=updated.unrefined_cultivation,
            revision=updated.revision,
        )


def _state(row: LifeCultivationStateRow) -> CultivationState:
    return CultivationState(
        life_id=row.life_id,
        current_level=row.current_level,
        unrefined_cultivation=row.unrefined_cultivation,
        realized_cultivation=row.realized_cultivation,
        active_session_id=row.active_session_id,
        revision=row.revision,
    )


def _technique(row: LifeTechniqueRow) -> LifeTechnique:
    return LifeTechnique(
        life_technique_id=row.life_technique_id,
        life_id=row.life_id,
        technique_id=row.technique_id,
        definition_version=row.definition_version,
        group_code=row.group_code,
        major_realm=row.major_realm,
        invested_amount=row.invested_amount,
        max_investment=row.max_investment,
        current_layer=row.current_layer,
        status=row.status,
    )


def _realm_entry(row: LifeRealmEntryRow) -> RealmEntry:
    return RealmEntry(
        realm_entry_id=row.realm_entry_id,
        life_id=row.life_id,
        generation=row.generation,
        parent_entry_id=row.parent_entry_id,
        source_level=row.source_level,
        target_level=row.target_level,
        source_group=row.source_group,
        target_group=row.target_group,
        source_floor=row.source_floor,
        target_baseline=row.target_baseline,
        transition_kind=row.transition_kind,
        transition_session_id=row.transition_session_id,
        status=row.status,
        invalidated_at=row.invalidated_at,
    )


def _resource_entry_type(changes: tuple[TechniqueInvestmentChange, ...]) -> str:
    entry_types = {change.entry_type for change in changes}
    if entry_types == {"seclusion_realization"}:
        return "seclusion_realization"
    if entry_types <= {"abandonment"}:
        return "technique_abandonment"
    if entry_types <= {"transfer_in", "transfer_out"}:
        return "technique_transfer"
    if entry_types == {"breakthrough_penalty"}:
        return "breakthrough_penalty"
    if entry_types == {"administrative_adjustment"}:
        return "administrative_adjustment"
    raise ValueError("Technique investment entry types cannot share one operation")
