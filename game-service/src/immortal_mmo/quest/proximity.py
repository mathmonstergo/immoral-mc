from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from immortal_mmo.quest.models import (
    PROXIMITY_QUEST_STATES,
    ProximityBarkRule,
    QuestStateCondition,
    RealmLevelCondition,
)


@dataclass(frozen=True, slots=True)
class ProximityEvaluationContext:
    quest_states: Mapping[str, str]
    current_realm_level: int

    def __post_init__(self) -> None:
        normalized_states = dict(self.quest_states)
        if any(state not in PROXIMITY_QUEST_STATES for state in normalized_states.values()):
            raise ValueError("Proximity context contains an unknown quest state")
        if (
            isinstance(self.current_realm_level, bool)
            or not isinstance(self.current_realm_level, int)
            or not 0 <= self.current_realm_level <= 22
        ):
            raise ValueError("current_realm_level must be between 0 and 22")
        object.__setattr__(
            self,
            "quest_states",
            MappingProxyType(normalized_states),
        )


def select_proximity_bark_rule(
    rules: Sequence[ProximityBarkRule],
    context: ProximityEvaluationContext,
) -> ProximityBarkRule | None:
    ordered = sorted(
        enumerate(rules),
        key=lambda item: (-item[1].priority, item[0]),
    )
    return next(
        (
            rule
            for _, rule in ordered
            if all(_condition_matches(condition, context) for condition in rule.conditions)
        ),
        None,
    )


def _condition_matches(
    condition: QuestStateCondition | RealmLevelCondition,
    context: ProximityEvaluationContext,
) -> bool:
    if isinstance(condition, QuestStateCondition):
        return context.quest_states.get(condition.quest_id) in condition.states
    if isinstance(condition, RealmLevelCondition):
        return (
            condition.minimum_level is None
            or context.current_realm_level >= condition.minimum_level
        ) and (
            condition.maximum_level is None
            or context.current_realm_level <= condition.maximum_level
        )
    raise TypeError(f"Unsupported proximity condition: {type(condition)!r}")
