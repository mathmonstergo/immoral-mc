from dataclasses import replace

import pytest

from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestObjectiveDefinition,
    QuestObjectiveType,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
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
            QuestObjectiveDefinition(
                objective_id="detect-spirit-root",
                objective_type=QuestObjectiveType.CURRENT_LIFE_SPIRIT_ROOT_PRESENT,
                label="灵根检测",
                required=1,
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
