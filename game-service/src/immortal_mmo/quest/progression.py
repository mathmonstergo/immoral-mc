from datetime import datetime
from uuid import UUID

from immortal_mmo.core.errors import ConflictError
from immortal_mmo.core.uow import UnitOfWork
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import MythicMobKillObjectiveDefinition
from immortal_mmo.quest.repository import QuestObjectiveProgress, QuestProgressStatus


class QuestObjectiveProgressMismatchError(ConflictError):
    code = "quest.objective_progress_mismatch"
    message = "Stored quest objective progress does not match its definition."


class QuestEventProgressionService:
    def __init__(self, catalog: QuestDefinitionCatalog = QUEST_CATALOG) -> None:
        self._catalog = catalog

    async def record_mythicmob_kill(
        self,
        uow: UnitOfWork,
        *,
        life_id: UUID,
        mob_internal_name: str,
        occurred_at: datetime,
    ) -> bool:
        if not any(
            isinstance(objective, MythicMobKillObjectiveDefinition)
            for quest in self._catalog.quests
            for objective in quest.objectives
        ):
            return False
        quest_ids = {
            quest.quest_id
            for quest in self._catalog.quests
            if any(
                isinstance(objective, MythicMobKillObjectiveDefinition)
                for objective in quest.objectives
            )
        }
        await uow.quests.get_quest_revision(life_id, for_update=True)
        progresses = await uow.quests.get_progresses(life_id, quest_ids)
        objective_progresses = await uow.quests.get_objective_progresses(
            life_id,
            quest_ids,
        )
        eligible: list[tuple[str, MythicMobKillObjectiveDefinition]] = []
        for quest in self._catalog.quests:
            progress = progresses.get(quest.quest_id)
            event_objectives = tuple(
                objective
                for objective in quest.objectives
                if isinstance(objective, MythicMobKillObjectiveDefinition)
            )
            if progress is None:
                continue
            if progress.definition_version != quest.version:
                raise QuestObjectiveProgressMismatchError()
            for objective in event_objectives:
                stored = objective_progresses.get((quest.quest_id, objective.objective_id))
                self._validate_stored_progress(progress.life_id, quest.version, objective, stored)
                if (
                    progress.status is not QuestProgressStatus.ACTIVE
                    or objective.mob_internal_name != mob_internal_name
                    or occurred_at < progress.accepted_at
                    or stored.current_value >= objective.required_count
                ):
                    continue
                eligible.append((quest.quest_id, objective))

        if not eligible:
            return False

        updated = await uow.quests.increment_objective_progresses(
            life_id=life_id,
            objectives=tuple(
                (quest_id, objective.objective_id) for quest_id, objective in eligible
            ),
            updated_at=occurred_at,
        )
        if set(updated) != {
            (quest_id, objective.objective_id) for quest_id, objective in eligible
        }:
            raise QuestObjectiveProgressMismatchError()
        await uow.quests.increment_quest_revision(life_id)
        return True

    @staticmethod
    def _validate_stored_progress(
        life_id: UUID,
        definition_version: int,
        objective: MythicMobKillObjectiveDefinition,
        stored: QuestObjectiveProgress | None,
    ) -> None:
        if (
            stored is None
            or stored.life_id != life_id
            or stored.definition_version != definition_version
            or stored.objective_type != objective.objective_type.value
            or stored.target_id != objective.mob_internal_name
            or stored.required_value != objective.required_count
        ):
            raise QuestObjectiveProgressMismatchError()
