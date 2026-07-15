from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

AttributionKind = Literal[
    "direct",
    "projectile",
    "damage_over_time",
    "summon",
    "trap",
    "formation",
    "bukkit_fallback",
]
TelemetryMode = Literal["compact", "detailed"]
CombatKillOutcome = Literal[
    "accepted",
    "duplicate",
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
