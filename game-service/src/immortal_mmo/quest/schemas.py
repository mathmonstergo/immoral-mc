from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator

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


class QuestMutationRequest(BaseModel):
    provider_id: str


class QuestRevisionVector(BaseModel):
    player: int
    quest: int
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


class QuestMutationResult(BaseModel):
    operation_id: UUID
    changed: bool
    quest: ProviderQuestState
    interaction_state: QuestInteractionState
