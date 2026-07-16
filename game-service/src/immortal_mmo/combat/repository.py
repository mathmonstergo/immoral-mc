from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.combat.models import CombatKillEvent


class CombatRepository(Protocol):
    async def get_event(self, source_event_id: UUID) -> CombatKillEvent | None: ...

    async def insert_event_if_absent(self, event: CombatKillEvent) -> bool: ...

    async def finalize_reward_result(
        self,
        kill_event_id: UUID,
        *,
        credited_cultivation_amount: int,
        unrefined_balance_after: int,
    ) -> None: ...

    async def increment_mob_counter(
        self,
        life_id: UUID,
        mob_internal_name: str,
        occurred_at: datetime,
    ) -> int: ...
