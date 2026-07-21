from dataclasses import replace

import pytest

from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    CurrentLifeSpiritRootObjectiveDefinition,
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    ProximityBarkRule,
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestObjectiveType,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
    QuestStateCondition,
    RealmLevelCondition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)


def quest(quest_id: str, category: QuestCategory = QuestCategory.MAIN) -> QuestDefinition:
    return QuestDefinition(
        quest_id=quest_id,
        version=1,
        title=quest_id,
        description=f"{quest_id} description",
        category=category,
        repeatability=QuestRepeatability.ONCE_PER_LIFE,
        prerequisites=(),
        objectives=(
            CurrentLifeSpiritRootObjectiveDefinition(
                objective_id="detect-spirit-root",
                label="灵根检测",
            ),
        ),
        provider_ids=("provider",),
        turn_in_provider_ids=("provider",),
        dialogue_keys=QuestDialogueKeys(
            available=f"{quest_id}.available",
            active=f"{quest_id}.active",
            ready_to_turn_in=f"{quest_id}.ready",
            completed=f"{quest_id}.completed",
        ),
        presentation=QuestPresentationHints(
            active_next_action="前往鉴灵师处",
            ready_next_action="返回老村民处",
        ),
    )


def provider(*quest_ids: str) -> QuestProviderDefinition:
    return QuestProviderDefinition(
        provider_id="provider",
        display_name="Provider",
        main_quest_ids=tuple(quest_ids),
        side_quest_ids=(),
    )


def test_runtime_catalog_contains_first_steps_and_old_man() -> None:
    first_steps = QUEST_CATALOG.get_quest("first-steps")
    old_man = QUEST_CATALOG.get_provider("old-man")

    assert first_steps.title == "初入凡尘"
    assert first_steps.category is QuestCategory.MAIN
    assert first_steps.repeatability is QuestRepeatability.ONCE_PER_LIFE
    assert first_steps.objectives[0].objective_id == "detect-spirit-root"
    assert (
        first_steps.objectives[0].objective_type
        is QuestObjectiveType.CURRENT_LIFE_SPIRIT_ROOT_PRESENT
    )
    assert old_man.main_quest_ids == ("first-steps",)
    assert old_man.side_quest_ids == ()
    assert [rule.rule_id for rule in old_man.proximity_bark_rules] == [
        "first-steps-available",
        "first-steps-active",
        "first-steps-ready",
    ]
    assert QUEST_CATALOG.revision.startswith("sha256:")
    assert len(QUEST_CATALOG.revision) == len("sha256:") + 64


def test_definition_digest_is_stable_across_input_order() -> None:
    first = quest("first")
    second = quest("second")
    catalog_a = QuestDefinitionCatalog(
        quests=(first, second),
        providers=(provider("first", "second"),),
    )
    catalog_b = QuestDefinitionCatalog(
        quests=(second, first),
        providers=(provider("first", "second"),),
    )

    assert catalog_a.revision == catalog_b.revision


@pytest.mark.parametrize(
    ("quests", "providers", "message"),
    [
        ((quest("same"), quest("same")), (provider("same"),), "Duplicate quest ID"),
        ((quest("known"),), (provider("missing"),), "Unknown quest ID"),
        (
            (quest("overlap"),),
            (
                replace(
                    provider("overlap"),
                    side_quest_ids=("overlap",),
                ),
            ),
            "both main and side",
        ),
    ],
)
def test_catalog_rejects_invalid_content(
    quests: tuple[QuestDefinition, ...],
    providers: tuple[QuestProviderDefinition, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        QuestDefinitionCatalog(quests=quests, providers=providers)


def test_provider_preserves_ordered_main_and_side_quests() -> None:
    main_a = quest("main-a")
    main_b = quest("main-b")
    side = quest("side", QuestCategory.SIDE)
    synthetic = QuestProviderDefinition(
        provider_id="provider",
        display_name="Provider",
        main_quest_ids=("main-b", "main-a"),
        side_quest_ids=("side",),
    )

    catalog = QuestDefinitionCatalog(
        quests=(main_a, main_b, side),
        providers=(synthetic,),
    )

    assert catalog.get_provider("provider").ordered_quest_ids == (
        "main-b",
        "main-a",
        "side",
    )


def test_typed_objectives_expose_validated_projection_targets() -> None:
    objectives = (
        ItemDeliveryObjectiveDefinition("deliver", "交付筑基丹", "foundation_pill", 3),
        MythicMobKillObjectiveDefinition("hunt", "击杀苍狼", "AzureWolf", 5),
        TechniqueLayerObjectiveDefinition("train", "修炼功法", "Gongfa_68726c", 7),
        RealmLevelObjectiveDefinition("realm", "提升境界", 14),
    )

    assert tuple(objective.required for objective in objectives) == (3, 5, 7, 14)
    assert tuple(objective.objective_type for objective in objectives) == (
        QuestObjectiveType.ITEM_DELIVERY,
        QuestObjectiveType.MYTHICMOB_KILL_COUNT,
        QuestObjectiveType.TECHNIQUE_LAYER_REACHED,
        QuestObjectiveType.REALM_LEVEL_REACHED,
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ItemDeliveryObjectiveDefinition("item", "Item", "bad item", 1),
        lambda: MythicMobKillObjectiveDefinition("kill", "Kill", "AzureWolf", 0),
        lambda: TechniqueLayerObjectiveDefinition("technique", "Technique", "GF_01", 14),
        lambda: RealmLevelObjectiveDefinition("realm", "Realm", 23),
    ],
)
def test_typed_objectives_reject_invalid_targets(factory) -> None:
    with pytest.raises(ValueError):
        factory()


def test_catalog_rejects_duplicate_objective_targets() -> None:
    duplicate = replace(
        quest("duplicate-objective"),
        objectives=(
            ItemDeliveryObjectiveDefinition("first", "First", "foundation_pill", 1),
            ItemDeliveryObjectiveDefinition("second", "Second", "foundation_pill", 2),
        ),
    )

    with pytest.raises(ValueError, match="Duplicate objective target"):
        QuestDefinitionCatalog(
            quests=(duplicate,),
            providers=(provider("duplicate-objective"),),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("provider_ids", (), "at least one provider"),
        ("turn_in_provider_ids", (), "at least one turn-in provider"),
        ("provider_ids", ("provider", "provider"), "Duplicate provider ID"),
        (
            "turn_in_provider_ids",
            ("provider", "provider"),
            "Duplicate turn-in provider ID",
        ),
    ],
)
def test_catalog_rejects_invalid_quest_provider_relationships(
    field: str,
    value: tuple[str, ...],
    message: str,
) -> None:
    invalid = replace(quest("invalid-provider-relationship"), **{field: value})

    with pytest.raises(ValueError, match=message):
        QuestDefinitionCatalog(
            quests=(invalid,),
            providers=(provider(invalid.quest_id),),
        )


def test_catalog_rejects_quest_missing_from_declared_provider() -> None:
    first = quest("first")
    missing = quest("missing")

    with pytest.raises(ValueError, match="Quest missing is missing from provider provider"):
        QuestDefinitionCatalog(
            quests=(first, missing),
            providers=(provider("first"),),
        )


def test_catalog_rejects_provider_without_matching_quest_relationship() -> None:
    definition = quest("listed-by-extra-provider")
    extra = QuestProviderDefinition(
        provider_id="extra",
        display_name="Extra",
        main_quest_ids=(definition.quest_id,),
        side_quest_ids=(),
    )

    with pytest.raises(ValueError, match="without a matching quest relationship"):
        QuestDefinitionCatalog(
            quests=(definition,),
            providers=(provider(definition.quest_id), extra),
        )


def test_catalog_rejects_more_objectives_than_the_sidebar_can_render() -> None:
    oversized = replace(
        quest("oversized"),
        objectives=tuple(
            ItemDeliveryObjectiveDefinition(
                f"item-{index}",
                f"Item {index}",
                f"item_{index}",
                1,
            )
            for index in range(13)
        ),
    )

    with pytest.raises(ValueError, match="at most 12 objectives"):
        QuestDefinitionCatalog(
            quests=(oversized,),
            providers=(provider("oversized"),),
        )


def test_catalog_rejects_unknown_quest_in_proximity_rule() -> None:
    known = quest("known")
    invalid_provider = replace(
        provider("known"),
        proximity_bark_rules=(
            ProximityBarkRule(
                rule_id="missing-quest",
                text="Missing",
                conditions=(QuestStateCondition("missing", ("completed",)),),
            ),
        ),
    )

    with pytest.raises(ValueError, match="Unknown proximity bark quest ID"):
        QuestDefinitionCatalog(quests=(known,), providers=(invalid_provider,))


@pytest.mark.parametrize(
    "factory",
    [
        lambda: QuestStateCondition("quest", ()),
        lambda: QuestStateCondition("quest", ("unknown",)),
        lambda: RealmLevelCondition(),
        lambda: RealmLevelCondition(minimum_level=-1),
        lambda: RealmLevelCondition(minimum_level=5, maximum_level=4),
        lambda: ProximityBarkRule("rule", " "),
        lambda: ProximityBarkRule("rule", "Text", cooldown_seconds=0),
        lambda: ProximityBarkRule(
            "rule",
            "Text",
            conditions=(
                RealmLevelCondition(minimum_level=1),
                RealmLevelCondition(maximum_level=5),
            ),
        ),
    ],
)
def test_proximity_rule_definitions_reject_invalid_content(factory) -> None:
    with pytest.raises(ValueError):
        factory()


def test_provider_rejects_duplicate_proximity_rule_ids() -> None:
    rule = ProximityBarkRule("same", "Text")

    with pytest.raises(ValueError, match="Duplicate proximity bark rule ID"):
        replace(provider("quest"), proximity_bark_rules=(rule, rule))


def test_proximity_bark_key_accepts_the_256_character_boundary() -> None:
    provider_id = "p" * 128
    rule_id = "r" * 127
    definition = replace(
        provider("quest"),
        provider_id=provider_id,
        proximity_bark_rules=(ProximityBarkRule(rule_id, "Text"),),
    )
    key = f"{definition.provider_id}:{definition.proximity_bark_rules[0].rule_id}"

    assert len(key) == 256


@pytest.mark.parametrize(
    "factory",
    [
        lambda: replace(provider("quest"), provider_id="provider:branch"),
        lambda: ProximityBarkRule("rule:branch", "Text"),
    ],
)
def test_proximity_bark_key_components_reject_the_separator(factory) -> None:
    with pytest.raises(ValueError, match="must not contain ':'"):
        factory()


def test_proximity_bark_key_rejects_a_length_above_the_wire_limit() -> None:
    provider_id = "p" * 128
    rule_id = "r" * 128

    with pytest.raises(ValueError, match="must not exceed 256 characters"):
        replace(
            provider("quest"),
            provider_id=provider_id,
            proximity_bark_rules=(ProximityBarkRule(rule_id, "Text"),),
        )
