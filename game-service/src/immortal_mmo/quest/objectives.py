from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from immortal_mmo.quest.models import (
    CurrentLifeSpiritRootObjectiveDefinition,
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestObjectiveDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)

ObjectiveProgressKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class QuestEvaluationContext:
    spirit_root_present: bool
    item_quantities: Mapping[str, int]
    kill_progress: Mapping[ObjectiveProgressKey, int]
    active_technique_layers: Mapping[str, int]
    current_realm_level: int
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_quantities", MappingProxyType(dict(self.item_quantities)))
        object.__setattr__(self, "kill_progress", MappingProxyType(dict(self.kill_progress)))
        object.__setattr__(
            self,
            "active_technique_layers",
            MappingProxyType(dict(self.active_technique_layers)),
        )


@dataclass(frozen=True, slots=True)
class ObjectiveEvaluation:
    current: int
    required: int

    @property
    def completed(self) -> bool:
        return self.current >= self.required


def evaluate_objective(
    quest_id: str,
    objective: QuestObjectiveDefinition,
    context: QuestEvaluationContext,
) -> ObjectiveEvaluation:
    if isinstance(objective, CurrentLifeSpiritRootObjectiveDefinition):
        current = 1 if context.spirit_root_present else 0
    elif isinstance(objective, ItemDeliveryObjectiveDefinition):
        current = context.item_quantities.get(objective.item_code, 0)
    elif isinstance(objective, MythicMobKillObjectiveDefinition):
        current = context.kill_progress.get((quest_id, objective.objective_id), 0)
    elif isinstance(objective, TechniqueLayerObjectiveDefinition):
        current = context.active_technique_layers.get(objective.technique_id, 0)
    elif isinstance(objective, RealmLevelObjectiveDefinition):
        current = context.current_realm_level
    else:
        raise TypeError(f"Unsupported quest objective definition: {type(objective)!r}")
    return ObjectiveEvaluation(current=current, required=objective.required)
