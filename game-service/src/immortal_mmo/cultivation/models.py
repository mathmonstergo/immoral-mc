from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CombatCultivationCredit:
    entry_id: UUID | None
    life_id: UUID
    kill_event_id: UUID
    amount: int
    balance_after: int
    revision: int


@dataclass(frozen=True, slots=True)
class CultivationState:
    life_id: UUID
    current_level: int
    unrefined_cultivation: int
    realized_cultivation: int
    active_session_id: UUID | None
    revision: int


@dataclass(frozen=True, slots=True)
class LifeTechnique:
    life_technique_id: UUID
    life_id: UUID
    technique_id: str
    definition_version: int
    group_code: str
    major_realm: str
    invested_amount: int
    max_investment: int
    current_layer: int
    status: str


@dataclass(frozen=True, slots=True)
class RealmEntry:
    realm_entry_id: UUID
    life_id: UUID
    generation: int
    parent_entry_id: UUID | None
    source_level: int
    target_level: int
    source_group: str
    target_group: str
    source_floor: int
    target_baseline: int
    transition_kind: str
    transition_session_id: UUID | None
    status: str
    invalidated_at: datetime | None


@dataclass(frozen=True, slots=True)
class CultivationSession:
    session_id: UUID
    life_id: UUID
    session_kind: str
    status: str
    idempotency_key: UUID
    request_fingerprint: str
    area_id: str | None
    content_version: str
    source_level: int
    target_level: int | None
    frozen_snapshot: dict[str, object]
    cumulative_elapsed_seconds: int
    cumulative_generated: int
    cumulative_reserve_consumed: int
    cumulative_retained: int
    started_at: datetime
    completes_at: datetime
    settled_at: datetime | None
    revision: int


@dataclass(frozen=True, slots=True)
class TechniqueInvestmentChange:
    life_technique_id: UUID
    delta_amount: int
    entry_type: str


@dataclass(frozen=True, slots=True)
class SessionTechnique:
    session_id: UUID
    life_id: UUID
    life_technique_id: UUID
    definition_version: int
    group_code: str
    major_realm: str
    frozen_capacity: int
    frozen_invested: int
    frozen_full_mastery_seconds: int
