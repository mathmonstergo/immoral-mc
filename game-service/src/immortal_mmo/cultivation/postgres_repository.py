from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.combat.catalog import MAX_REWARD_AMOUNT
from immortal_mmo.cultivation.db_models import (
    CultivationResourceEntryRow,
    LifeCultivationStateRow,
)
from immortal_mmo.cultivation.models import CombatCultivationCredit


class PostgresCultivationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def credit_combat_reward(
        self,
        *,
        life_id: UUID,
        kill_event_id: UUID,
        amount: int,
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
        if state.unrefined_cultivation > MAX_REWARD_AMOUNT - amount:
            raise ValueError("Unrefined cultivation balance overflow")

        balance_after = state.unrefined_cultivation + amount
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
        entry_id = uuid4()
        self._session.add(
            CultivationResourceEntryRow(
                entry_id=entry_id,
                life_id=life_id,
                resource_code="unrefined_cultivation",
                entry_type="combat_reward",
                delta_amount=amount,
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
            amount=amount,
            balance_after=updated.unrefined_cultivation,
            revision=updated.revision,
        )
