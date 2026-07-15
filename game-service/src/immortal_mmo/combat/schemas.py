from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from immortal_mmo.combat.models import AttributionKind, CombatKillOutcome

MAX_MOB_LEVEL = Decimal("999999999.999")
InternalName = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"),
]


class CombatKillEventRequest(BaseModel):
    contract_version: Literal[1] = 1
    event_id: UUID
    server_id: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]
    entity_uuid: UUID
    mob_internal_name: InternalName
    mob_level: Decimal
    killer_uuid: UUID
    source_life_id: UUID | None = None
    attribution_kind: AttributionKind
    technique_id: InternalName | None = None
    cast_id: UUID | None = None
    world: Annotated[str, Field(min_length=1, max_length=128)]
    x: Annotated[float, Field(allow_inf_nan=False)]
    y: Annotated[float, Field(allow_inf_nan=False)]
    z: Annotated[float, Field(allow_inf_nan=False)]
    occurred_at: datetime

    @field_validator("mob_level", mode="before")
    @classmethod
    def parse_decimal_string(cls, value: object) -> Decimal:
        if not isinstance(value, str):
            raise ValueError("mob_level must be a decimal string")
        try:
            level = Decimal(value)
        except InvalidOperation as error:
            raise ValueError("mob_level must be a decimal string") from error
        if not level.is_finite() or level < 0 or level > MAX_MOB_LEVEL:
            raise ValueError("mob_level is outside supported bounds")
        if level.as_tuple().exponent < -3:
            raise ValueError("mob_level has more than three decimal places")
        return level

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class CombatKillBatchRequest(BaseModel):
    contract_version: Literal[1] = 1
    events: Annotated[list[CombatKillEventRequest], Field(min_length=1, max_length=200)]

    @field_validator("events")
    @classmethod
    def reject_duplicate_event_ids(
        cls,
        events: list[CombatKillEventRequest],
    ) -> list[CombatKillEventRequest]:
        event_ids = [event.event_id for event in events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("events contains duplicate event_id")
        return events


class CombatKillResult(BaseModel):
    event_id: UUID
    outcome: CombatKillOutcome
    kill_event_id: UUID
    life_id: UUID | None = None
    reward_amount: Annotated[int | None, Field(gt=0)] = None
    unrefined_balance: Annotated[int | None, Field(ge=0)] = None

    @model_validator(mode="after")
    def validate_reward_shape(self) -> "CombatKillResult":
        if self.outcome == "accepted" and (
            self.life_id is None
            or self.reward_amount is None
            or self.unrefined_balance is None
        ):
            raise ValueError("accepted combat kill result requires reward fields")
        if self.outcome in {
            "not_rewardable",
            "account_not_found",
            "current_life_unavailable",
        } and (self.reward_amount is not None or self.unrefined_balance is not None):
            raise ValueError("no-reward combat kill result cannot include reward fields")
        return self


class CombatKillBatchResponse(BaseModel):
    contract_version: Literal[1] = 1
    results: list[CombatKillResult]
