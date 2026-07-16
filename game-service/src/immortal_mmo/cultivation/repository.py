from collections.abc import Collection
from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.cultivation.models import (
    CombatCultivationCredit,
    CultivationSession,
    CultivationState,
    LifeTechnique,
    RealmEntry,
    TechniqueInvestmentChange,
)


class CultivationRepository(Protocol):
    async def get_or_create_state(self, life_id: UUID, *, for_update: bool) -> CultivationState: ...

    async def get_techniques(
        self,
        life_id: UUID,
        technique_ids: Collection[UUID] = (),
        *,
        for_update: bool,
    ) -> tuple[LifeTechnique, ...]: ...

    async def get_active_realm_chain(
        self, life_id: UUID, *, for_update: bool
    ) -> tuple[RealmEntry, ...]: ...

    async def get_group_investments(self, life_id: UUID) -> dict[str, int]: ...

    async def insert_session(self, session: CultivationSession) -> None: ...

    async def apply_technique_investments(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        session_id: UUID | None,
        changes: tuple[TechniqueInvestmentChange, ...],
        occurred_at: datetime,
    ) -> CultivationState: ...

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
        cap: int,
        occurred_at: datetime,
    ) -> CombatCultivationCredit: ...
