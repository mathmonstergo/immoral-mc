from dataclasses import dataclass
from enum import StrEnum


class QuestCategory(StrEnum):
    MAIN = "main"
    SIDE = "side"


class QuestRepeatability(StrEnum):
    ONCE_PER_LIFE = "once_per_life"


class QuestObjectiveType(StrEnum):
    CURRENT_LIFE_SPIRIT_ROOT_PRESENT = "current_life_spirit_root_present"


@dataclass(frozen=True, slots=True)
class QuestObjectiveDefinition:
    objective_id: str
    objective_type: QuestObjectiveType
    label: str
    required: int

    def __post_init__(self) -> None:
        if self.required < 1:
            raise ValueError("Quest objective required value must be positive")


@dataclass(frozen=True, slots=True)
class QuestDialogueKeys:
    available: str
    active: str
    ready_to_turn_in: str
    completed: str


@dataclass(frozen=True, slots=True)
class QuestPresentationHints:
    active_next_action: str
    ready_next_action: str
    available_proximity_text: str
    active_proximity_text: str
    ready_proximity_text: str


@dataclass(frozen=True, slots=True)
class QuestDefinition:
    quest_id: str
    version: int
    title: str
    category: QuestCategory
    repeatability: QuestRepeatability
    prerequisites: tuple[str, ...]
    objectives: tuple[QuestObjectiveDefinition, ...]
    provider_ids: tuple[str, ...]
    turn_in_provider_ids: tuple[str, ...]
    dialogue_keys: QuestDialogueKeys
    presentation: QuestPresentationHints


@dataclass(frozen=True, slots=True)
class QuestProviderDefinition:
    provider_id: str
    display_name: str
    main_quest_ids: tuple[str, ...]
    side_quest_ids: tuple[str, ...]

    @property
    def ordered_quest_ids(self) -> tuple[str, ...]:
        return self.main_quest_ids + self.side_quest_ids
