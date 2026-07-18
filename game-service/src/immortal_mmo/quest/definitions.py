import hashlib
import json
from dataclasses import asdict
from types import MappingProxyType
from typing import Any

from immortal_mmo.quest.models import (
    CurrentLifeSpiritRootObjectiveDefinition,
    QuestCategory,
    QuestDefinition,
    QuestDialogueKeys,
    QuestPresentationHints,
    QuestProviderDefinition,
    QuestRepeatability,
    objective_target_key,
)

MAX_OBJECTIVES_PER_QUEST = 12


class QuestDefinitionCatalog:
    def __init__(
        self,
        *,
        quests: tuple[QuestDefinition, ...],
        providers: tuple[QuestProviderDefinition, ...],
    ) -> None:
        self._validate(quests, providers)
        self._quests = MappingProxyType(
            {
                quest.quest_id: quest
                for quest in sorted(quests, key=lambda item: item.quest_id)
            }
        )
        self._providers = MappingProxyType(
            {
                provider.provider_id: provider
                for provider in sorted(providers, key=lambda item: item.provider_id)
            }
        )
        self.revision = self._build_revision(quests, providers)

    @property
    def quests(self) -> tuple[QuestDefinition, ...]:
        return tuple(self._quests.values())

    @property
    def providers(self) -> tuple[QuestProviderDefinition, ...]:
        return tuple(self._providers.values())

    def get_quest(self, quest_id: str) -> QuestDefinition:
        return self._quests[quest_id]

    def find_quest(self, quest_id: str) -> QuestDefinition | None:
        return self._quests.get(quest_id)

    def get_provider(self, provider_id: str) -> QuestProviderDefinition:
        return self._providers[provider_id]

    def find_provider(self, provider_id: str) -> QuestProviderDefinition | None:
        return self._providers.get(provider_id)

    @staticmethod
    def _validate(
        quests: tuple[QuestDefinition, ...],
        providers: tuple[QuestProviderDefinition, ...],
    ) -> None:
        quest_ids = [quest.quest_id for quest in quests]
        if len(quest_ids) != len(set(quest_ids)):
            raise ValueError("Duplicate quest ID")

        provider_ids = [provider.provider_id for provider in providers]
        if len(provider_ids) != len(set(provider_ids)):
            raise ValueError("Duplicate provider ID")

        known_quest_ids = set(quest_ids)
        known_provider_ids = set(provider_ids)
        for quest in quests:
            if quest.version <= 0:
                raise ValueError(f"Quest version must be positive: {quest.quest_id}")
            if not quest.provider_ids:
                raise ValueError(f"Quest must have at least one provider: {quest.quest_id}")
            if not quest.turn_in_provider_ids:
                raise ValueError(
                    f"Quest must have at least one turn-in provider: {quest.quest_id}"
                )
            if len(quest.provider_ids) != len(set(quest.provider_ids)):
                raise ValueError(f"Duplicate provider ID in quest {quest.quest_id}")
            if len(quest.turn_in_provider_ids) != len(set(quest.turn_in_provider_ids)):
                raise ValueError(f"Duplicate turn-in provider ID in quest {quest.quest_id}")
            if not quest.objectives:
                raise ValueError(f"Quest must have at least one objective: {quest.quest_id}")
            if len(quest.objectives) > MAX_OBJECTIVES_PER_QUEST:
                raise ValueError(
                    f"Quest supports at most {MAX_OBJECTIVES_PER_QUEST} objectives: "
                    f"{quest.quest_id}"
                )
            objective_ids = [objective.objective_id for objective in quest.objectives]
            if len(objective_ids) != len(set(objective_ids)):
                raise ValueError(f"Duplicate objective ID in quest {quest.quest_id}")
            target_keys = [objective_target_key(objective) for objective in quest.objectives]
            if len(target_keys) != len(set(target_keys)):
                raise ValueError(f"Duplicate objective target in quest {quest.quest_id}")
            unknown_prerequisites = set(quest.prerequisites) - known_quest_ids
            if unknown_prerequisites:
                raise ValueError(f"Unknown prerequisite quest ID: {unknown_prerequisites}")
            if set(quest.provider_ids) - known_provider_ids:
                raise ValueError(f"Unknown provider ID for quest {quest.quest_id}")
            if set(quest.turn_in_provider_ids) - known_provider_ids:
                raise ValueError(f"Unknown turn-in provider ID for quest {quest.quest_id}")

        for provider in providers:
            main_ids = provider.main_quest_ids
            side_ids = provider.side_quest_ids
            if len(main_ids) != len(set(main_ids)) or len(side_ids) != len(set(side_ids)):
                raise ValueError(f"Duplicate quest ID in provider {provider.provider_id}")
            if set(main_ids) & set(side_ids):
                raise ValueError(f"Quest is in both main and side lists for {provider.provider_id}")
            unknown_ids = set(provider.ordered_quest_ids) - known_quest_ids
            if unknown_ids:
                raise ValueError(
                    f"Unknown quest ID in provider {provider.provider_id}: {unknown_ids}"
                )

        quests_by_id = {quest.quest_id: quest for quest in quests}
        providers_by_id = {provider.provider_id: provider for provider in providers}
        for quest in quests:
            for provider_id in set(quest.provider_ids) | set(quest.turn_in_provider_ids):
                if quest.quest_id not in providers_by_id[provider_id].ordered_quest_ids:
                    raise ValueError(
                        f"Quest {quest.quest_id} is missing from provider {provider_id}"
                    )
        for provider in providers:
            for quest_id in provider.ordered_quest_ids:
                quest = quests_by_id[quest_id]
                if (
                    provider.provider_id not in quest.provider_ids
                    and provider.provider_id not in quest.turn_in_provider_ids
                ):
                    raise ValueError(
                        f"Provider {provider.provider_id} lists quest {quest_id} "
                        "without a matching quest relationship"
                    )

    @staticmethod
    def _build_revision(
        quests: tuple[QuestDefinition, ...],
        providers: tuple[QuestProviderDefinition, ...],
    ) -> str:
        normalized: dict[str, list[dict[str, Any]]] = {
            "quests": [asdict(quest) for quest in sorted(quests, key=lambda item: item.quest_id)],
            "providers": [
                asdict(provider)
                for provider in sorted(providers, key=lambda item: item.provider_id)
            ],
        }
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return f"sha256:{hashlib.sha256(serialized).hexdigest()}"


FIRST_STEPS = QuestDefinition(
    quest_id="first-steps",
    version=1,
    title="初入凡尘",
    category=QuestCategory.MAIN,
    repeatability=QuestRepeatability.ONCE_PER_LIFE,
    prerequisites=(),
    objectives=(
        CurrentLifeSpiritRootObjectiveDefinition(
            objective_id="detect-spirit-root",
            label="灵根检测",
        ),
    ),
    provider_ids=("old-man",),
    turn_in_provider_ids=("old-man",),
    dialogue_keys=QuestDialogueKeys(
        available="first-steps.available",
        active="first-steps.active",
        ready_to_turn_in="first-steps.ready_to_turn_in",
        completed="first-steps.completed",
    ),
    presentation=QuestPresentationHints(
        active_next_action="前往鉴灵师处",
        ready_next_action="返回老村民处",
        available_proximity_text="最近太不太平了...",
        active_proximity_text="去找鉴灵师看看吧。",
        ready_proximity_text="看来你已经有所收获。",
    ),
)

OLD_MAN = QuestProviderDefinition(
    provider_id="old-man",
    display_name="老村民",
    main_quest_ids=("first-steps",),
    side_quest_ids=(),
)

QUEST_CATALOG = QuestDefinitionCatalog(
    quests=(FIRST_STEPS,),
    providers=(OLD_MAN,),
)
