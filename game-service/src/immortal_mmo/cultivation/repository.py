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
    SessionTechnique,
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

    async def get_latest_realm_generation(self, life_id: UUID) -> int: ...

    async def append_realm_entry(self, entry: RealmEntry) -> CultivationState: ...

    async def insert_session(self, session: CultivationSession) -> None: ...

    async def start_session(
        self,
        session: CultivationSession,
        techniques: tuple[SessionTechnique, ...],
    ) -> None: ...

    async def get_session(
        self, session_id: UUID, *, for_update: bool
    ) -> CultivationSession | None: ...

    async def get_session_by_idempotency(
        self, life_id: UUID, idempotency_key: UUID
    ) -> CultivationSession | None: ...

    async def get_session_techniques(self, session_id: UUID) -> tuple[SessionTechnique, ...]: ...

    async def consume_unrefined(
        self,
        *,
        life_id: UUID,
        session_id: UUID,
        operation_id: UUID,
        amount: int,
        occurred_at: datetime,
    ) -> CultivationState: ...

    async def update_session_settlement(
        self,
        *,
        session_id: UUID,
        cumulative_elapsed_seconds: int,
        cumulative_generated: int,
        cumulative_reserve_consumed: int,
        cumulative_retained: int,
        status: str,
        settled_at: datetime | None,
    ) -> CultivationSession: ...

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
