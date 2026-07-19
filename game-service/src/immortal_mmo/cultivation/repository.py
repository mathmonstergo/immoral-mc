from collections.abc import Collection
from datetime import datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.cultivation.models import (
    BreakthroughTechniqueDebit,
    CombatCultivationCredit,
    CultivationSession,
    CultivationState,
    LifeTechnique,
    QuestCultivationRewardClaim,
    QuestCultivationRewardGrant,
    RealmEntry,
    SessionTechnique,
    TechniqueInvestmentChange,
    TechniqueLearnOperation,
)


class ActiveCultivationSessionExists(RuntimeError):
    """Raised when a life already owns an open cultivation session."""


class CultivationRepository(Protocol):
    async def claim_pending_quest_reward(
        self,
        *,
        operation_id: UUID,
        grant_id: UUID,
        life_id: UUID,
        cap: int,
        occurred_at: datetime,
    ) -> QuestCultivationRewardClaim: ...

    async def finalize_quest_reward_claim(
        self,
        *,
        operation_id: UUID,
        response_body: bytes,
    ) -> QuestCultivationRewardClaim: ...

    async def get_learn_operation(
        self,
        operation_id: UUID,
    ) -> TechniqueLearnOperation | None: ...

    async def learn_technique(
        self,
        *,
        operation: TechniqueLearnOperation,
        technique: LifeTechnique,
    ) -> LifeTechnique: ...

    async def finalize_learn_operation(
        self,
        *,
        operation_id: UUID,
        response_body: bytes,
    ) -> TechniqueLearnOperation: ...

    async def grant_quest_reward(
        self,
        *,
        grant_id: UUID,
        life_id: UUID,
        operation_id: UUID,
        quest_id: str,
        reward_id: str,
        configured_amount: int,
        cap: int,
        occurred_at: datetime,
    ) -> QuestCultivationRewardGrant: ...

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

    async def has_realm_transition_history(
        self,
        life_id: UUID,
        *,
        source_level: int,
        target_level: int,
    ) -> bool: ...

    async def append_realm_entry(self, entry: RealmEntry) -> CultivationState: ...

    async def invalidate_realm_suffix(
        self,
        *,
        life_id: UUID,
        retained_entry_ids: tuple[UUID, ...],
        current_level: int,
        invalidated_at: datetime,
    ) -> CultivationState: ...

    async def abandon_technique(
        self,
        *,
        life_id: UUID,
        life_technique_id: UUID,
    ) -> CultivationState: ...

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

    async def store_breakthrough_debits(
        self,
        debits: tuple[BreakthroughTechniqueDebit, ...],
    ) -> None: ...

    async def get_breakthrough_debits(
        self, session_id: UUID
    ) -> tuple[BreakthroughTechniqueDebit, ...]: ...

    async def update_session_frozen_snapshot(
        self,
        *,
        session_id: UUID,
        frozen_snapshot: dict[str, object],
    ) -> CultivationSession: ...

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
