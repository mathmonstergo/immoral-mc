from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

AttributionKind = Literal[
    "direct",
    "projectile",
    "damage_over_time",
    "summon",
    "trap",
    "formation",
]
TelemetryMode = Literal["compact", "detailed"]
CombatKillOutcome = Literal[
    "accepted",
    "duplicate",
    "not_rewardable",
    "account_not_found",
    "current_life_unavailable",
]
StoredCombatKillOutcome = Literal[
    "rewarded",
    "not_rewardable",
    "account_not_found",
    "current_life_unavailable",
]


@dataclass(frozen=True, slots=True)
class RewardDecision:
    amount: int
    telemetry: TelemetryMode
    profile_id: str
    mob_level: Decimal


@dataclass(frozen=True, slots=True)
class CombatKillEvent:
    kill_event_id: UUID
    source_event_id: UUID
    request_fingerprint: str
    server_id: str
    entity_uuid: UUID
    mob_internal_name: str
    mob_level: Decimal
    killer_minecraft_uuid: UUID
    source_life_id: UUID | None
    attribution_kind: AttributionKind
    technique_id: str | None
    cast_id: UUID | None
    account_id: UUID | None
    life_id: UUID | None
    world_key: str
    occurred_at: datetime
    outcome: StoredCombatKillOutcome
    telemetry: TelemetryMode
    detail_payload: dict[str, object] | None
    configured_reward_amount: int | None
    credited_cultivation_amount: int | None
    unrefined_balance_after: int | None
