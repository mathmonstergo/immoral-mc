from dataclasses import replace

import pytest

from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    CurrentLifeSpiritRootObjectiveDefinition,
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestObjectiveType,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)


def quest(quest_id: str, category: QuestCategory = QuestCategory.MAIN) -> QuestDefinition:
    return QuestDefinition(
        quest_id=quest_id,
        version=1,
        title=quest_id,
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
            available_proximity_text="最近太不太平了...",
            active_proximity_text="去找鉴灵师看看吧。",
            ready_proximity_text="看来你已经有所收获。",
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
