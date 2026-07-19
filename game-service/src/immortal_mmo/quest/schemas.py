from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from immortal_mmo.quest.models import QuestCategory

QuestState = Literal[
    "unavailable",
    "available",
    "active",
    "ready_to_turn_in",
    "completed",
]
QuestAction = Literal["none", "offer", "remind", "turn_in", "talk"]


class QuestInteractionStateRequest(BaseModel):
    provider_ids: list[str]

    @field_validator("provider_ids")
    @classmethod
    def normalize_provider_ids(cls, provider_ids: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(provider_ids))
        if len(normalized) > 32:
            raise ValueError("provider_ids contains more than 32 unique providers")
        return normalized


class QuestProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str


class QuestTurnInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    inventory_item_instance_ids: list[UUID] = Field(max_length=256)

    @field_validator("inventory_item_instance_ids")
    @classmethod
    def unique_inventory_items(cls, values: list[UUID]) -> list[UUID]:
        if len(values) != len(set(values)):
            raise ValueError("inventory_item_instance_ids must be unique")
        return values


class QuestRevisionVector(BaseModel):
    player: int
    quest: int
    objectives: int
    definitions: str


class QuestObjectiveProjection(BaseModel):
    objective_id: str
    title: str
    current: int
    required: int
    completed: bool


class ProviderQuestState(BaseModel):
    quest_id: str
    title: str
    category: QuestCategory
    state: QuestState
    action: QuestAction
    dialogue_key: str | None
    objectives: list[QuestObjectiveProjection]


class ProximityBark(BaseModel):
    key: str
    speaker: str
    text: str
    cooldown_seconds: int


class QuestProviderProjection(BaseModel):
    provider_id: str
    state_key: str
    quests: list[ProviderQuestState]
    actionable_quest_ids: list[str]
    direct_action_quest_id: str | None
    proximity_bark: ProximityBark | None


class TrackedQuest(BaseModel):
    quest_id: str
    title: str
    state: Literal["active", "ready_to_turn_in"]
    objectives: list[QuestObjectiveProjection]
    next_action_hint: str


class QuestInteractionState(BaseModel):
    contract_version: Literal[1] = 1
    account_id: UUID
    life_id: UUID
    revision: QuestRevisionVector
    providers: list[QuestProviderProjection]
    tracked_quest: TrackedQuest | None
    cache_ttl_ms: int = 2000


class QuestRewardResult(BaseModel):
    grant_id: UUID
    reward_id: str
    kind: Literal["fixed_item", "unrefined_cultivation"]
    status: Literal["applied", "pending"]
    item_code: str | None
    quantity: int | None
    item_instance_ids: list[UUID]
    cultivation_amount: int | None
    applied_amount: int = Field(ge=0)
    pending_amount: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_reward_shape(self) -> "QuestRewardResult":
        if (self.status == "applied" and self.pending_amount != 0) or (
            self.status == "pending" and self.pending_amount == 0
        ):
            raise ValueError("reward status does not match pending_amount")
        if self.kind == "fixed_item":
            if (
                not self.item_code
                or self.quantity is None
                or self.quantity <= 0
                or len(self.item_instance_ids) != self.quantity
                or self.cultivation_amount is not None
                or self.applied_amount != 0
                or self.pending_amount != self.quantity
            ):
                raise ValueError("fixed item reward shape is invalid")
            return self
        if (
            self.item_code is not None
            or self.quantity is not None
            or self.item_instance_ids
            or self.cultivation_amount is None
            or self.cultivation_amount <= 0
            or self.applied_amount + self.pending_amount != self.cultivation_amount
        ):
            raise ValueError("cultivation reward shape is invalid")
        return self


class QuestMutationResult(BaseModel):
    operation_id: UUID
    changed: bool
    quest: ProviderQuestState
    interaction_state: QuestInteractionState
    rewards: list[QuestRewardResult]
    consumed_item_instance_ids: list[UUID]


class QuestProviderTemplate(BaseModel):
    provider_id: str
    display_name: str
    main_quest_ids: list[str]
    side_quest_ids: list[str]


class QuestProviderCatalog(BaseModel):
    contract_version: Literal[1] = 1
    revision: str
    providers: list[QuestProviderTemplate]
