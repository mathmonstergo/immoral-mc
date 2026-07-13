from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from immortal_mmo.core.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    RuleViolationError,
)
from immortal_mmo.player.schemas import CurrentLifeQuestFacts
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    QuestCategory,
    QuestDefinition,
    QuestProviderDefinition,
)
from immortal_mmo.quest.repository import (
    FrozenQuestDomainError,
    InMemoryQuestRepository,
    OperationIdConflictError,
    QuestFinalizedFailure,
    QuestFinalizedOperation,
    QuestOperationAttempt,
    QuestOperationCommand,
    QuestOperationOwner,
    QuestOperationProjectionContext,
    QuestOperationState,
    QuestOperationWaiter,
    QuestProgress,
    QuestProgressSnapshot,
    QuestProgressStatus,
    QuestRepository,
)
from immortal_mmo.quest.schemas import (
    ProviderQuestState,
    ProximityBark,
    QuestInteractionState,
    QuestMutationResult,
    QuestObjectiveProjection,
    QuestProviderCatalog,
    QuestProviderProjection,
    QuestProviderTemplate,
    QuestRevisionVector,
    TrackedQuest,
)


class CurrentLifeFactsReader(Protocol):
    def get_current_life_facts(self, account_id: UUID) -> CurrentLifeQuestFacts: ...


QuestProjectionFacts = CurrentLifeQuestFacts | QuestOperationProjectionContext


class QuestNotFoundError(NotFoundError):
    code = "quest.not_found"
    message = "Quest was not found."


class QuestProviderNotFoundError(NotFoundError):
    code = "quest.provider_not_found"
    message = "Quest provider was not found."


class QuestProviderMismatchError(ConflictError):
    code = "quest.provider_mismatch"
    message = "Quest is not available from this provider."


class QuestNotAvailableError(RuleViolationError):
    code = "quest.not_available"
    message = "Quest is not available."


class QuestNotAcceptedError(RuleViolationError):
    code = "quest.not_accepted"
    message = "Quest has not been accepted."


class QuestNotReadyError(RuleViolationError):
    code = "quest.not_ready"
    message = "Quest objectives are not complete."


class QuestIdempotencyConflictError(ConflictError):
    code = "quest.idempotency_conflict"
    message = "Idempotency key was already used for a different operation."


class QuestService:
    def __init__(
        self,
        player_facts_reader: CurrentLifeFactsReader,
        repository: QuestRepository | None = None,
        catalog: QuestDefinitionCatalog = QUEST_CATALOG,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._player_facts_reader = player_facts_reader
        self._repository = repository or InMemoryQuestRepository()
        self._catalog = catalog
        self._clock = clock or (lambda: datetime.now(UTC))

    def get_provider_catalog(self) -> QuestProviderCatalog:
        return QuestProviderCatalog(
            revision=self._catalog.revision,
            providers=[
                QuestProviderTemplate(
                    provider_id=provider.provider_id,
                    display_name=provider.display_name,
                    main_quest_ids=list(provider.main_quest_ids),
                    side_quest_ids=list(provider.side_quest_ids),
                )
                for provider in self._catalog.providers
            ],
        )

    def get_interaction_state(
        self,
        account_id: UUID,
        provider_ids: Sequence[str],
    ) -> QuestInteractionState:
        normalized_provider_ids = tuple(dict.fromkeys(provider_ids))
        if len(normalized_provider_ids) > 32:
            raise ValueError("At most 32 quest providers may be inspected at once")
        self._resolve_providers(normalized_provider_ids)
        facts, snapshot = self._load_context(account_id)
        return self._build_interaction_state(
            facts,
            snapshot.progresses,
            snapshot.quest_revision,
            normalized_provider_ids,
        )

    def accept(
        self,
        account_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
    ) -> QuestMutationResult:
        facts = self._player_facts_reader.get_current_life_facts(account_id)
        context = self._projection_context(facts)
        attempt = self._reserve_operation(
            facts.life_id,
            operation_id,
            QuestOperationCommand.ACCEPT,
            quest_id,
            provider_id,
            context,
        )
        resolved = self._wait_or_replay(
            attempt,
            QuestOperationCommand.ACCEPT,
            quest_id,
            provider_id,
            context,
        )
        if isinstance(resolved, QuestMutationResult):
            return resolved
        owner = resolved
        if owner.state.mutation_attached:
            return self._finalize_success(owner)
        try:
            quest, _ = self._resolve_mutation_target(quest_id, provider_id, turn_in=False)
            snapshot = self._load_progress_snapshot(facts)
            current = self._project_quest(quest, facts, snapshot.progresses)
            if current.state == "unavailable":
                raise QuestNotAvailableError()
            owner = self._repository.attach_accept_mutation(
                owner,
                definition_version=quest.version,
                accepted_at=self._clock(),
                projection_quest_ids=self._catalog_quest_ids(),
            )
        except DomainError as exc:
            self._finalize_failure_and_raise(owner, exc)
        except Exception:
            self._repository.release_operation_owner(owner)
            raise
        return self._finalize_success(owner)

    def turn_in(
        self,
        account_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
    ) -> QuestMutationResult:
        facts = self._player_facts_reader.get_current_life_facts(account_id)
        context = self._projection_context(facts)
        attempt = self._reserve_operation(
            facts.life_id,
            operation_id,
            QuestOperationCommand.TURN_IN,
            quest_id,
            provider_id,
            context,
        )
        resolved = self._wait_or_replay(
            attempt,
            QuestOperationCommand.TURN_IN,
            quest_id,
            provider_id,
            context,
        )
        if isinstance(resolved, QuestMutationResult):
            return resolved
        owner = resolved
        if owner.state.mutation_attached:
            return self._finalize_success(owner)
        try:
            quest, _ = self._resolve_mutation_target(quest_id, provider_id, turn_in=True)
            snapshot = self._load_progress_snapshot(facts)
            current = self._project_quest(quest, facts, snapshot.progresses)
            if current.state in {"unavailable", "available"}:
                raise QuestNotAcceptedError()
            if current.state == "active":
                raise QuestNotReadyError()
            owner = self._repository.attach_complete_mutation(
                owner,
                completed_at=self._clock(),
                projection_quest_ids=self._catalog_quest_ids(),
            )
        except DomainError as exc:
            self._finalize_failure_and_raise(owner, exc)
        except Exception:
            self._repository.release_operation_owner(owner)
            raise
        return self._finalize_success(owner)

    def _load_context(
        self,
        account_id: UUID,
    ) -> tuple[CurrentLifeQuestFacts, QuestProgressSnapshot]:
        facts = self._player_facts_reader.get_current_life_facts(account_id)
        return facts, self._load_progress_snapshot(facts)

    def _load_progress_snapshot(
        self,
        facts: CurrentLifeQuestFacts,
    ) -> QuestProgressSnapshot:
        snapshot = self._repository.get_progress_snapshot(
            facts.life_id,
            self._catalog_quest_ids(),
        )
        return snapshot

    def _catalog_quest_ids(self) -> set[str]:
        return {quest.quest_id for quest in self._catalog.quests}

    def _build_mutation_result(
        self,
        facts: QuestOperationProjectionContext,
        operation: QuestOperationState,
    ) -> QuestMutationResult:
        if not operation.mutation_attached:
            raise RuntimeError("Quest mutation state is not attached")
        assert operation.snapshot is not None
        assert operation.progress is not None
        assert operation.changed is not None
        interaction_state = self._build_interaction_state(
            facts,
            operation.snapshot.progresses,
            operation.snapshot.quest_revision,
            (operation.provider_id,),
        )
        quest_projection = next(
            quest
            for quest in interaction_state.providers[0].quests
            if quest.quest_id == operation.progress.quest_id
        )
        return QuestMutationResult(
            operation_id=operation.operation_id,
            changed=operation.changed,
            quest=quest_projection,
            interaction_state=interaction_state,
        )

    @staticmethod
    def _result_from_repository_operation(
        operation: QuestFinalizedOperation,
    ) -> QuestMutationResult:
        if not operation.frozen_response_json:
            raise RuntimeError("Quest operation is missing its frozen response")
        return QuestMutationResult.model_validate_json(operation.frozen_response_json)

    def _reserve_operation(
        self,
        life_id: UUID,
        operation_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        context: QuestOperationProjectionContext,
    ) -> QuestOperationAttempt:
        try:
            return self._repository.reserve_operation(
                life_id=life_id,
                operation_id=operation_id,
                command=command,
                quest_id=quest_id,
                provider_id=provider_id,
                projection_context=context,
            )
        except OperationIdConflictError as exc:
            raise QuestIdempotencyConflictError() from exc

    def _wait_or_replay(
        self,
        attempt: QuestOperationAttempt,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        context: QuestOperationProjectionContext,
    ) -> QuestOperationOwner | QuestMutationResult:
        while True:
            if isinstance(attempt, QuestFinalizedOperation):
                return self._result_from_repository_operation(attempt)
            if isinstance(attempt, QuestFinalizedFailure):
                raise self._domain_error_from_frozen(attempt.error)
            if isinstance(attempt, QuestOperationWaiter):
                self._repository.wait_for_operation(attempt)
                attempt = self._reserve_operation(
                    attempt.life_id,
                    attempt.operation_id,
                    command,
                    quest_id,
                    provider_id,
                    context,
                )
                continue
            return attempt

    def _finalize_success(self, owner: QuestOperationOwner) -> QuestMutationResult:
        try:
            result = self._build_mutation_result(
                owner.state.projection_context,
                owner.state,
            )
            frozen_response_json = result.model_dump_json()
            finalized = self._repository.finalize_operation(owner, frozen_response_json)
        except Exception:
            self._repository.release_operation_owner(owner)
            raise
        return self._result_from_repository_operation(finalized)

    def _finalize_failure_and_raise(
        self,
        owner: QuestOperationOwner,
        error: DomainError,
    ) -> None:
        frozen = FrozenQuestDomainError(
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        )
        finalized = self._repository.finalize_failure(owner, frozen)
        raise self._domain_error_from_frozen(finalized.error)

    @staticmethod
    def _domain_error_from_frozen(error: FrozenQuestDomainError) -> DomainError:
        error_types: dict[str, type[DomainError]] = {
            QuestNotFoundError.code: QuestNotFoundError,
            QuestProviderNotFoundError.code: QuestProviderNotFoundError,
            QuestProviderMismatchError.code: QuestProviderMismatchError,
            QuestNotAvailableError.code: QuestNotAvailableError,
            QuestNotAcceptedError.code: QuestNotAcceptedError,
            QuestNotReadyError.code: QuestNotReadyError,
        }
        error_type = error_types.get(error.code, DomainError)
        restored = error_type(error.message)
        restored.status_code = error.status_code
        restored.code = error.code
        restored.retryable = error.retryable
        return restored

    @staticmethod
    def _projection_context(
        facts: CurrentLifeQuestFacts,
    ) -> QuestOperationProjectionContext:
        return QuestOperationProjectionContext(
            account_id=facts.account_id,
            life_id=facts.life_id,
            revision=facts.revision,
            spirit_root_present=facts.spirit_root is not None,
        )

    def _build_interaction_state(
        self,
        facts: QuestProjectionFacts,
        progresses: dict[str, QuestProgress],
        quest_revision: int,
        provider_ids: Sequence[str],
    ) -> QuestInteractionState:
        providers = [
            self._project_provider(self._catalog.get_provider(provider_id), facts, progresses)
            for provider_id in provider_ids
        ]
        return QuestInteractionState(
            account_id=facts.account_id,
            life_id=facts.life_id,
            revision=QuestRevisionVector(
                player=facts.revision,
                quest=quest_revision,
                definitions=self._catalog.revision,
            ),
            providers=providers,
            tracked_quest=self._project_tracked_quest(facts, progresses),
        )

    def _project_provider(
        self,
        provider: QuestProviderDefinition,
        facts: QuestProjectionFacts,
        progresses: dict[str, QuestProgress],
    ) -> QuestProviderProjection:
        provider_order = {
            quest_id: index for index, quest_id in enumerate(provider.ordered_quest_ids)
        }
        quests = [
            self._project_quest(
                self._catalog.get_quest(quest_id),
                facts,
                progresses,
                provider,
            )
            for quest_id in provider.ordered_quest_ids
        ]
        quests.sort(key=lambda item: self._actionable_sort_key(item, provider_order))
        actionable = [
            quest.quest_id
            for quest in quests
            if quest.action in {"offer", "remind", "turn_in"}
        ]
        lead = next(
            (
                quest
                for quest in quests
                if quest.action in {"offer", "remind", "turn_in"}
            ),
            None,
        )
        return QuestProviderProjection(
            provider_id=provider.provider_id,
            state_key=(f"{lead.quest_id}:{lead.state}" if lead else f"{provider.provider_id}:none"),
            quests=quests,
            actionable_quest_ids=actionable,
            direct_action_quest_id=actionable[0] if len(actionable) == 1 else None,
            proximity_bark=self._project_proximity_bark(provider, lead),
        )

    def _project_quest(
        self,
        quest: QuestDefinition,
        facts: QuestProjectionFacts,
        progresses: dict[str, QuestProgress],
        provider: QuestProviderDefinition | None = None,
    ) -> ProviderQuestState:
        objective_projections = [
            self._project_objective(
                objective.objective_id,
                objective.label,
                objective.required,
                facts,
            )
            for objective in quest.objectives
        ]
        progress = progresses.get(quest.quest_id)
        if progress is not None and progress.status is QuestProgressStatus.COMPLETED:
            state = "completed"
        elif progress is not None and all(item.completed for item in objective_projections):
            state = "ready_to_turn_in"
        elif progress is not None:
            state = "active"
        elif all(
            progresses.get(prerequisite) is not None
            and progresses[prerequisite].status is QuestProgressStatus.COMPLETED
            for prerequisite in quest.prerequisites
        ):
            state = "available"
        else:
            state = "unavailable"

        action = self._provider_action(quest, provider, state)
        dialogue_by_state = {
            "unavailable": None,
            "available": quest.dialogue_keys.available,
            "active": quest.dialogue_keys.active,
            "ready_to_turn_in": quest.dialogue_keys.ready_to_turn_in,
            "completed": quest.dialogue_keys.completed,
        }
        return ProviderQuestState(
            quest_id=quest.quest_id,
            title=quest.title,
            category=quest.category,
            state=state,
            action=action,
            dialogue_key=dialogue_by_state[state] if action != "none" else None,
            objectives=objective_projections,
        )

    def _project_objective(
        self,
        objective_id: str,
        label: str,
        required: int,
        facts: QuestProjectionFacts,
    ) -> QuestObjectiveProjection:
        spirit_root_present = (
            facts.spirit_root_present
            if isinstance(facts, QuestOperationProjectionContext)
            else facts.spirit_root is not None
        )
        current = 1 if spirit_root_present else 0
        return QuestObjectiveProjection(
            objective_id=objective_id,
            title=label,
            current=current,
            required=required,
            completed=current >= required,
        )

    def _project_tracked_quest(
        self,
        facts: QuestProjectionFacts,
        progresses: dict[str, QuestProgress],
    ) -> TrackedQuest | None:
        candidates = [
            (index, quest, self._project_quest(quest, facts, progresses))
            for index, quest in enumerate(self._catalog.quests)
        ]
        candidates = [
            item
            for item in candidates
            if item[2].state in {"active", "ready_to_turn_in"}
        ]
        if not candidates:
            return None
        _, definition, projection = min(
            candidates,
            key=lambda item: (
                0 if item[2].state == "ready_to_turn_in" else 1,
                0 if item[1].category is QuestCategory.MAIN else 1,
                item[0],
            ),
        )
        next_action = (
            definition.presentation.ready_next_action
            if projection.state == "ready_to_turn_in"
            else definition.presentation.active_next_action
        )
        return TrackedQuest(
            quest_id=projection.quest_id,
            title=projection.title,
            state=projection.state,
            objectives=projection.objectives,
            next_action_hint=next_action,
        )

    def _project_proximity_bark(
        self,
        provider: QuestProviderDefinition,
        quest: ProviderQuestState | None,
    ) -> ProximityBark | None:
        if quest is None or quest.state not in {"available", "active", "ready_to_turn_in"}:
            return None
        definition = self._catalog.get_quest(quest.quest_id)
        text_by_state = {
            "available": definition.presentation.available_proximity_text,
            "active": definition.presentation.active_proximity_text,
            "ready_to_turn_in": definition.presentation.ready_proximity_text,
        }
        return ProximityBark(
            key=f"{quest.quest_id}:{quest.state}",
            speaker=provider.display_name,
            text=text_by_state[quest.state],
            cooldown_seconds=60,
        )

    @staticmethod
    def _provider_action(
        quest: QuestDefinition,
        provider: QuestProviderDefinition | None,
        state: str,
    ) -> str:
        if provider is None:
            return {
                "unavailable": "none",
                "available": "offer",
                "active": "remind",
                "ready_to_turn_in": "turn_in",
                "completed": "talk",
            }[state]

        provider_id = provider.provider_id
        is_giver = provider_id in quest.provider_ids
        is_turn_in = provider_id in quest.turn_in_provider_ids
        if state == "available":
            return "offer" if is_giver else "none"
        if state == "active":
            return "remind" if is_giver or is_turn_in else "none"
        if state == "ready_to_turn_in":
            if is_turn_in:
                return "turn_in"
            return "remind" if is_giver else "none"
        if state == "completed":
            return "talk" if is_giver or is_turn_in else "none"
        return "none"

    @staticmethod
    def _actionable_sort_key(
        quest: ProviderQuestState,
        provider_order: dict[str, int],
    ) -> tuple[int, int, int]:
        state_rank = {
            "ready_to_turn_in": 0,
            "active": 1,
            "available": 2,
            "completed": 3,
            "unavailable": 4,
        }[quest.state]
        category_rank = 0 if quest.category is QuestCategory.MAIN else 1
        return state_rank, category_rank, provider_order[quest.quest_id]

    def _resolve_providers(
        self,
        provider_ids: Sequence[str],
    ) -> tuple[QuestProviderDefinition, ...]:
        providers = []
        for provider_id in provider_ids:
            provider = self._catalog.find_provider(provider_id)
            if provider is None:
                raise QuestProviderNotFoundError()
            providers.append(provider)
        return tuple(providers)

    def _resolve_mutation_target(
        self,
        quest_id: str,
        provider_id: str,
        *,
        turn_in: bool,
    ) -> tuple[QuestDefinition, QuestProviderDefinition]:
        quest = self._catalog.find_quest(quest_id)
        if quest is None:
            raise QuestNotFoundError()
        provider = self._catalog.find_provider(provider_id)
        if provider is None:
            raise QuestProviderNotFoundError()
        allowed_provider_ids = quest.turn_in_provider_ids if turn_in else quest.provider_ids
        if provider_id not in allowed_provider_ids or quest_id not in provider.ordered_quest_ids:
            raise QuestProviderMismatchError()
        return quest, provider
