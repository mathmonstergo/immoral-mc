from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from immortal_mmo.quest.models import (
    MAX_PROXIMITY_BARK_KEY_LENGTH,
    QuestCategory,
    QuestObjectiveType,
)

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
    expected_life_id: UUID


class QuestTurnInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    expected_life_id: UUID
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
    objective_type: QuestObjectiveType
    title: str
    item_code: str | None
    current: int
    required: int
    completed: bool

    @model_validator(mode="after")
    def validate_objective_shape(self) -> "QuestObjectiveProjection":
        if self.objective_type is QuestObjectiveType.ITEM_DELIVERY:
            if not self.item_code:
                raise ValueError("item-delivery objective must expose item_code")
        elif self.item_code is not None:
            raise ValueError("non-item objective must not expose item_code")
        return self


class QuestRewardPreview(BaseModel):
    reward_id: str
    kind: Literal["fixed_item", "unrefined_cultivation"]
    item_code: str | None
    quantity: int | None
    cultivation_amount: int | None

    @model_validator(mode="after")
    def validate_reward_shape(self) -> "QuestRewardPreview":
        if self.kind == "fixed_item":
            if (
                not self.item_code
                or self.quantity is None
                or self.quantity <= 0
                or self.cultivation_amount is not None
            ):
                raise ValueError("fixed item reward preview shape is invalid")
            return self
        if (
            self.item_code is not None
            or self.quantity is not None
            or self.cultivation_amount is None
            or self.cultivation_amount <= 0
        ):
            raise ValueError("cultivation reward preview shape is invalid")
        return self


class ProviderQuestState(BaseModel):
    quest_id: str
    title: str
    description: str
    category: QuestCategory
    state: QuestState
    action: QuestAction
    dialogue_key: str | None
    objectives: list[QuestObjectiveProjection]
    reward_previews: list[QuestRewardPreview]


class ProximityBark(BaseModel):
    key: str = Field(min_length=1, max_length=MAX_PROXIMITY_BARK_KEY_LENGTH)
    speaker: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=512)
    cooldown_seconds: int = Field(ge=1, le=86_400)

    @field_validator("key", "speaker", "text")
    @classmethod
    def require_trimmed_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("proximity bark text fields must be trimmed")
        return value


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
    contract_version: Literal[2] = 2
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
