from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.combat.db_models import CombatKillEventRow, LifeMobKillCounterRow
from immortal_mmo.combat.models import CombatKillEvent


class PostgresCombatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_event(self, source_event_id: UUID) -> CombatKillEvent | None:
        row = await self._session.scalar(
            select(CombatKillEventRow).where(
                CombatKillEventRow.source_type == "mythicmob_death",
                CombatKillEventRow.source_event_id == source_event_id,
            )
        )
        return _event_from_row(row) if row is not None else None

    async def insert_event_if_absent(self, event: CombatKillEvent) -> bool:
        inserted = await self._session.scalar(
            insert(CombatKillEventRow)
            .values(
                kill_event_id=event.kill_event_id,
                source_type="mythicmob_death",
                source_event_id=event.source_event_id,
                request_fingerprint=event.request_fingerprint,
                server_id=event.server_id,
                entity_uuid=event.entity_uuid,
                mob_internal_name=event.mob_internal_name,
                mob_level=event.mob_level,
                killer_minecraft_uuid=event.killer_minecraft_uuid,
                source_life_id=event.source_life_id,
                attribution_kind=event.attribution_kind,
                technique_id=event.technique_id,
                cast_id=event.cast_id,
                account_id=event.account_id,
                life_id=event.life_id,
                world_key=event.world_key,
                occurred_at=event.occurred_at,
                outcome=event.outcome,
                telemetry=event.telemetry,
                detail_payload=event.detail_payload,
                reward_amount=event.reward_amount,
            )
            .on_conflict_do_nothing(constraint="uq_combat_kill_source")
            .returning(CombatKillEventRow.kill_event_id)
        )
        return inserted is not None

    async def increment_mob_counter(
        self,
        life_id: UUID,
        mob_internal_name: str,
        occurred_at: datetime,
    ) -> int:
        counter_insert = insert(LifeMobKillCounterRow).values(
            life_id=life_id,
            mob_internal_name=mob_internal_name,
            kill_count=1,
            first_killed_at=occurred_at,
            last_killed_at=occurred_at,
        )
        count = await self._session.scalar(
            counter_insert.on_conflict_do_update(
                index_elements=[
                    LifeMobKillCounterRow.life_id,
                    LifeMobKillCounterRow.mob_internal_name,
                ],
                set_={
                    "kill_count": LifeMobKillCounterRow.kill_count + 1,
                    "last_killed_at": func.greatest(
                        LifeMobKillCounterRow.last_killed_at,
                        counter_insert.excluded.last_killed_at,
                    ),
                },
            ).returning(LifeMobKillCounterRow.kill_count)
        )
        if count is None:
            raise RuntimeError("Mob kill counter upsert returned no row")
        return count


def _event_from_row(row: CombatKillEventRow) -> CombatKillEvent:
    return CombatKillEvent(
        kill_event_id=row.kill_event_id,
        source_event_id=row.source_event_id,
        request_fingerprint=row.request_fingerprint,
        server_id=row.server_id,
        entity_uuid=row.entity_uuid,
        mob_internal_name=row.mob_internal_name,
        mob_level=row.mob_level,
        killer_minecraft_uuid=row.killer_minecraft_uuid,
        source_life_id=row.source_life_id,
        attribution_kind=row.attribution_kind,
        technique_id=row.technique_id,
        cast_id=row.cast_id,
        account_id=row.account_id,
        life_id=row.life_id,
        world_key=row.world_key,
        occurred_at=row.occurred_at,
        outcome=row.outcome,
        telemetry=row.telemetry,
        detail_payload=row.detail_payload,
        reward_amount=row.reward_amount,
    )
