from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.cultivation.models import CombatCultivationCredit


class CultivationRepository(Protocol):
    async def get_combat_credit(
        self,
        kill_event_id: UUID,
        life_id: UUID,
    ) -> CombatCultivationCredit | None: ...

    async def credit_combat_reward(
        self,
        *,
        life_id: UUID,
        kill_event_id: UUID,
        amount: int,
        occurred_at: datetime,
    ) -> CombatCultivationCredit: ...
