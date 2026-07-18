import re
from dataclasses import dataclass, field
from enum import StrEnum


class QuestCategory(StrEnum):
    MAIN = "main"
    SIDE = "side"


class QuestRepeatability(StrEnum):
    ONCE_PER_LIFE = "once_per_life"


class QuestObjectiveType(StrEnum):
    CURRENT_LIFE_SPIRIT_ROOT_PRESENT = "current_life_spirit_root_present"
    ITEM_DELIVERY = "item_delivery"
    MYTHICMOB_KILL_COUNT = "mythicmob_kill_count"
    TECHNIQUE_LAYER_REACHED = "technique_layer_reached"
    REALM_LEVEL_REACHED = "realm_level_reached"


@dataclass(frozen=True, slots=True)
class CurrentLifeSpiritRootObjectiveDefinition:
    objective_id: str
    label: str
    objective_type: QuestObjectiveType = field(
        init=False,
        default=QuestObjectiveType.CURRENT_LIFE_SPIRIT_ROOT_PRESENT,
    )
    required: int = field(init=False, default=1)

    def __post_init__(self) -> None:
        _validate_objective_identity(self.objective_id, self.label)


@dataclass(frozen=True, slots=True)
class ItemDeliveryObjectiveDefinition:
    objective_id: str
    label: str
    item_code: str
    required_quantity: int
    objective_type: QuestObjectiveType = field(
        init=False,
        default=QuestObjectiveType.ITEM_DELIVERY,
    )

    def __post_init__(self) -> None:
        _validate_objective_identity(self.objective_id, self.label)
        _validate_target_id(self.item_code, "item_code")
        _validate_positive_int(self.required_quantity, "required_quantity")

    @property
    def required(self) -> int:
        return self.required_quantity


@dataclass(frozen=True, slots=True)
class MythicMobKillObjectiveDefinition:
    objective_id: str
    label: str
    mob_internal_name: str
    required_count: int
    objective_type: QuestObjectiveType = field(
        init=False,
        default=QuestObjectiveType.MYTHICMOB_KILL_COUNT,
    )

    def __post_init__(self) -> None:
        _validate_objective_identity(self.objective_id, self.label)
        _validate_target_id(self.mob_internal_name, "mob_internal_name")
        _validate_positive_int(self.required_count, "required_count")

    @property
    def required(self) -> int:
        return self.required_count


@dataclass(frozen=True, slots=True)
class TechniqueLayerObjectiveDefinition:
    objective_id: str
    label: str
    technique_id: str
    target_layer: int
    objective_type: QuestObjectiveType = field(
        init=False,
        default=QuestObjectiveType.TECHNIQUE_LAYER_REACHED,
    )

    def __post_init__(self) -> None:
        _validate_objective_identity(self.objective_id, self.label)
        _validate_target_id(self.technique_id, "technique_id")
        _validate_positive_int(self.target_layer, "target_layer")
        if self.target_layer > 13:
            raise ValueError("target_layer must be between 1 and 13")

    @property
    def required(self) -> int:
        return self.target_layer


@dataclass(frozen=True, slots=True)
class RealmLevelObjectiveDefinition:
    objective_id: str
    label: str
    target_level: int
    objective_type: QuestObjectiveType = field(
        init=False,
        default=QuestObjectiveType.REALM_LEVEL_REACHED,
    )

    def __post_init__(self) -> None:
        _validate_objective_identity(self.objective_id, self.label)
        _validate_positive_int(self.target_level, "target_level")
        if self.target_level > 22:
            raise ValueError("target_level must be between 1 and 22")

    @property
    def required(self) -> int:
        return self.target_level


QuestObjectiveDefinition = (
    CurrentLifeSpiritRootObjectiveDefinition
    | ItemDeliveryObjectiveDefinition
    | MythicMobKillObjectiveDefinition
    | TechniqueLayerObjectiveDefinition
    | RealmLevelObjectiveDefinition
)


def objective_target_key(objective: QuestObjectiveDefinition) -> tuple[str, str]:
    if isinstance(objective, CurrentLifeSpiritRootObjectiveDefinition):
        target = "current-life"
    elif isinstance(objective, ItemDeliveryObjectiveDefinition):
        target = objective.item_code
    elif isinstance(objective, MythicMobKillObjectiveDefinition):
        target = objective.mob_internal_name
    elif isinstance(objective, TechniqueLayerObjectiveDefinition):
        target = objective.technique_id
    else:
        target = str(objective.target_level)
    return objective.objective_type.value, target


_TARGET_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _validate_objective_identity(objective_id: str, label: str) -> None:
    _validate_target_id(objective_id, "objective_id")
    if not label or label != label.strip() or len(label) > 128:
        raise ValueError("Quest objective label must be a trimmed non-empty string")


def _validate_target_id(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _TARGET_ID_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a stable identifier")


def _validate_positive_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


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
