from immortal_mmo.quest.models import (
    ProximityBarkRule,
    QuestStateCondition,
    RealmLevelCondition,
)
from immortal_mmo.quest.proximity import (
    ProximityEvaluationContext,
    select_proximity_bark_rule,
)


def test_rule_selection_uses_priority_then_stable_declaration_order() -> None:
    context = ProximityEvaluationContext(
        quest_states={"important": "active"},
        current_realm_level=3,
    )
    first_equal_priority = ProximityBarkRule(
        "first-equal",
        "First",
        conditions=(QuestStateCondition("important", ("active",)),),
        priority=10,
    )
    second_equal_priority = ProximityBarkRule(
        "second-equal",
        "Second",
        conditions=(QuestStateCondition("important", ("active",)),),
        priority=10,
    )
    higher_priority = ProximityBarkRule(
        "higher",
        "Higher",
        conditions=(RealmLevelCondition(minimum_level=4),),
        priority=20,
    )

    equal_priority_selected = select_proximity_bark_rule(
        (first_equal_priority, second_equal_priority, higher_priority),
        context,
    )
    higher_priority_selected = select_proximity_bark_rule(
        (first_equal_priority, second_equal_priority, higher_priority),
        ProximityEvaluationContext(
            quest_states={"important": "active"},
            current_realm_level=4,
        ),
    )

    assert equal_priority_selected is first_equal_priority
    assert higher_priority_selected is higher_priority


def test_rule_selection_ands_conditions_and_includes_realm_bounds() -> None:
    rule = ProximityBarkRule(
        "ready-foundation",
        "Ready",
        conditions=(
            QuestStateCondition("important", ("ready_to_turn_in", "completed")),
            RealmLevelCondition(minimum_level=9, maximum_level=12),
        ),
    )

    assert (
        select_proximity_bark_rule(
            (rule,),
            ProximityEvaluationContext(
                quest_states={"important": "ready_to_turn_in"},
                current_realm_level=9,
            ),
        )
        is rule
    )
    assert (
        select_proximity_bark_rule(
            (rule,),
            ProximityEvaluationContext(
                quest_states={"important": "completed"},
                current_realm_level=12,
            ),
        )
        is rule
    )
    assert (
        select_proximity_bark_rule(
            (rule,),
            ProximityEvaluationContext(
                quest_states={"important": "active"},
                current_realm_level=12,
            ),
        )
        is None
    )
    assert (
        select_proximity_bark_rule(
            (rule,),
            ProximityEvaluationContext(
                quest_states={"important": "completed"},
                current_realm_level=13,
            ),
        )
        is None
    )


def test_unconditional_rule_is_an_explicit_fallback_and_empty_rules_are_silent() -> None:
    fallback = ProximityBarkRule("fallback", "Fallback", priority=-10)
    context = ProximityEvaluationContext(
        quest_states={},
        current_realm_level=0,
    )

    assert select_proximity_bark_rule((), context) is None
    assert select_proximity_bark_rule((fallback,), context) is fallback
