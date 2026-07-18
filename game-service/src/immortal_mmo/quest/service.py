import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from immortal_mmo.core.error_wire import serialize_domain_error
from immortal_mmo.core.errors import ConflictError, DomainError, NotFoundError, RuleViolationError
from immortal_mmo.core.uow import UnitOfWork, UnitOfWorkFactory
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemOperationConflict,
)
from immortal_mmo.player.models import CurrentLifeQuestFacts
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestCategory,
    QuestDefinition,
    QuestProviderDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)
from immortal_mmo.quest.objectives import QuestEvaluationContext, evaluate_objective
from immortal_mmo.quest.progression import QuestObjectiveProgressMismatchError
from immortal_mmo.quest.repository import (
    FrozenHttpResponse,
    QuestObjectiveProgress,
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
    StoredQuestOperation,
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

RESPONSE_CONTENT_TYPE = "application/json"
RESPONSE_CONTRACT_VERSION = 1


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


class QuestDefinitionVersionMismatchError(ConflictError):
    code = "quest.definition_version_mismatch"
    message = "Quest progress uses a different definition version."


class QuestService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: QuestDefinitionCatalog = QUEST_CATALOG,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._clock = clock or (lambda: datetime.now(UTC))

    async def get_provider_catalog(self) -> QuestProviderCatalog:
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

    async def get_interaction_state(
        self,
        account_id: UUID,
        provider_ids: Sequence[str],
    ) -> QuestInteractionState:
        normalized_provider_ids = tuple(dict.fromkeys(provider_ids))
        if len(normalized_provider_ids) > 32:
            raise ValueError("At most 32 quest providers may be inspected at once")
        self._resolve_providers(normalized_provider_ids)
        async with self._uow_factory(isolation="repeatable_read") as uow:
            facts = await self._load_player_facts(uow, account_id, for_update=False)
            progresses = await uow.quests.get_progresses(facts.life_id, self._catalog_quest_ids())
            self._validate_progress_versions(progresses)
            objective_progresses = await uow.quests.get_objective_progresses(
                facts.life_id,
                self._catalog_quest_ids(),
            )
            self._validate_objective_progresses(progresses, objective_progresses)
            context = await self._load_evaluation_context(
                uow,
                facts,
                objective_progresses,
                lock_items=False,
            )
            quest_revision = await uow.quests.get_quest_revision(
                facts.life_id,
                for_update=False,
            )
            return self._build_interaction_state(
                facts,
                progresses,
                context,
                quest_revision,
                normalized_provider_ids,
            )

    async def accept(
        self,
        account_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
    ) -> FrozenHttpResponse:
        return await self._mutate(
            account_id,
            quest_id,
            provider_id,
            operation_id,
            QuestOperationCommand.ACCEPT,
        )

    async def turn_in(
        self,
        account_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
    ) -> FrozenHttpResponse:
        return await self._mutate(
            account_id,
            quest_id,
            provider_id,
            operation_id,
            QuestOperationCommand.TURN_IN,
        )

    async def _mutate(
        self,
        account_id: UUID,
        quest_id: str,
        provider_id: str,
        operation_id: UUID,
        command: QuestOperationCommand,
    ) -> FrozenHttpResponse:
        fingerprint = self._fingerprint(account_id, command, quest_id, provider_id)
        async with self._uow_factory(isolation="read_committed") as uow:
            existing = await uow.quests.get_operation(operation_id)
            if existing is not None:
                return self._replay(
                    existing,
                    account_id,
                    command,
                    quest_id,
                    provider_id,
                    fingerprint,
                )

            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            facts = await self._load_player_facts(uow, account_id, for_update=True)

            existing = await uow.quests.get_operation(operation_id)
            if existing is not None:
                return self._replay(
                    existing,
                    account_id,
                    command,
                    quest_id,
                    provider_id,
                    fingerprint,
                )

            operation = StoredQuestOperation(
                operation_id=operation_id,
                account_id=account_id,
                life_id=facts.life_id,
                command=command,
                quest_id=quest_id,
                provider_id=provider_id,
                request_fingerprint=fingerprint,
                state=QuestOperationState.PROCESSING,
                changed=None,
                response_status=None,
                response_content_type=None,
                response_body=None,
                response_contract_version=None,
                created_at=self._clock(),
                finalized_at=None,
            )
            if not await uow.quests.reserve_operation(operation):
                existing = await uow.quests.get_operation(operation_id)
                if existing is None:
                    raise RuntimeError("Reserved quest operation could not be loaded")
                return self._replay(
                    existing,
                    account_id,
                    command,
                    quest_id,
                    provider_id,
                    fingerprint,
                )

            try:
                response = await self._apply_mutation(uow, operation, facts)
                finalized = await uow.quests.finalize_operation(
                    operation_id,
                    state=QuestOperationState.SUCCEEDED,
                    changed=response[0],
                    response_status=200,
                    response_content_type=RESPONSE_CONTENT_TYPE,
                    response_body=response[1],
                    response_contract_version=RESPONSE_CONTRACT_VERSION,
                    finalized_at=self._clock(),
                )
            except DomainError as error:
                body = serialize_domain_error(error)
                finalized = await uow.quests.finalize_operation(
                    operation_id,
                    state=QuestOperationState.DOMAIN_FAILED,
                    changed=False,
                    response_status=error.status_code,
                    response_content_type=RESPONSE_CONTENT_TYPE,
                    response_body=body,
                    response_contract_version=RESPONSE_CONTRACT_VERSION,
                    finalized_at=self._clock(),
                )
            await uow.commit()
            return self._frozen_response(finalized)

    async def _apply_mutation(
        self,
        uow: UnitOfWork,
        operation: StoredQuestOperation,
        facts: CurrentLifeQuestFacts,
    ) -> tuple[bool, bytes]:
        turn_in = operation.command is QuestOperationCommand.TURN_IN
        quest, _ = self._resolve_mutation_target(
            operation.quest_id,
            operation.provider_id,
            turn_in=turn_in,
        )
        quest_revision = await uow.quests.get_quest_revision(facts.life_id, for_update=True)
        progresses = await uow.quests.get_progresses(facts.life_id, self._catalog_quest_ids())
        self._validate_progress_versions(progresses)
        objective_progresses = await uow.quests.get_objective_progresses(
            facts.life_id,
            self._catalog_quest_ids(),
        )
        self._validate_objective_progresses(progresses, objective_progresses)
        context = await self._load_evaluation_context(
            uow,
            facts,
            objective_progresses,
            lock_items=False,
        )
        progress = progresses.get(quest.quest_id)
        current = self._project_quest(quest, progresses, context)

        changed = False
        if operation.command is QuestOperationCommand.ACCEPT:
            if current.state == "unavailable":
                raise QuestNotAvailableError()
            if progress is None:
                accepted_at = self._clock()
                next_revision = quest_revision + 1
                changed = await uow.quests.insert_progress_if_absent(
                    QuestProgress(
                        life_id=facts.life_id,
                        quest_id=quest.quest_id,
                        definition_version=quest.version,
                        status=QuestProgressStatus.ACTIVE,
                        accepted_at=accepted_at,
                        completed_at=None,
                        revision=next_revision,
                    )
                )
                if changed:
                    await uow.quests.insert_objective_progresses(
                        self._initial_event_progresses(
                            facts.life_id,
                            quest,
                            accepted_at,
                        )
                    )
                    quest_revision = await uow.quests.increment_quest_revision(facts.life_id)
        else:
            if progress is None:
                raise QuestNotAcceptedError()
            if current.state == "active":
                raise QuestNotReadyError()
            if current.state == "ready_to_turn_in":
                completed_at = self._clock()
                await self._consume_delivery_items(
                    uow,
                    facts.life_id,
                    quest,
                    operation.operation_id,
                    completed_at,
                )
                next_revision = quest_revision + 1
                changed = await uow.quests.complete_progress_if_active(
                    facts.life_id,
                    quest.quest_id,
                    completed_at=completed_at,
                    revision=next_revision,
                )
                if not changed:
                    raise RuntimeError("Quest completion lost its active-state race")
                quest_revision = await uow.quests.increment_quest_revision(facts.life_id)

        progresses = await uow.quests.get_progresses(facts.life_id, self._catalog_quest_ids())
        objective_progresses = await uow.quests.get_objective_progresses(
            facts.life_id,
            self._catalog_quest_ids(),
        )
        self._validate_objective_progresses(progresses, objective_progresses)
        context = await self._load_evaluation_context(
            uow,
            facts,
            objective_progresses,
            lock_items=False,
        )
        quest_revision = await uow.quests.get_quest_revision(facts.life_id, for_update=True)
        interaction_state = self._build_interaction_state(
            facts,
            progresses,
            context,
            quest_revision,
            (operation.provider_id,),
        )
        quest_projection = next(
            projected
            for projected in interaction_state.providers[0].quests
            if projected.quest_id == operation.quest_id
        )
        result = QuestMutationResult(
            operation_id=operation.operation_id,
            changed=changed,
            quest=quest_projection,
            interaction_state=interaction_state,
        )
        return changed, result.model_dump_json().encode()

    async def _load_player_facts(
        self,
        uow: UnitOfWork,
        account_id: UUID,
        *,
        for_update: bool,
    ) -> CurrentLifeQuestFacts:
        facts = await uow.players.get_current_life_facts(account_id, for_update=for_update)
        if facts is not None:
            return facts
        account = await uow.players.lock_account(account_id)
        if account is None:
            raise PlayerAccountNotFoundError()
        raise PlayerLifecycleError()

    def _initial_event_progresses(
        self,
        life_id: UUID,
        quest: QuestDefinition,
        accepted_at: datetime,
    ) -> tuple[QuestObjectiveProgress, ...]:
        return tuple(
            QuestObjectiveProgress(
                life_id=life_id,
                quest_id=quest.quest_id,
                objective_id=objective.objective_id,
                definition_version=quest.version,
                objective_type=objective.objective_type.value,
                target_id=objective.mob_internal_name,
                required_value=objective.required_count,
                current_value=0,
                updated_at=accepted_at,
            )
            for objective in quest.objectives
            if isinstance(objective, MythicMobKillObjectiveDefinition)
        )

    async def _consume_delivery_items(
        self,
        uow: UnitOfWork,
        life_id: UUID,
        quest: QuestDefinition,
        operation_id: UUID,
        occurred_at: datetime,
    ) -> None:
        deliveries = sorted(
            (
                objective
                for objective in quest.objectives
                if isinstance(objective, ItemDeliveryObjectiveDefinition)
            ),
            key=lambda objective: objective.item_code,
        )
        try:
            await uow.items.consume_many(
                life_id=life_id,
                consumptions=tuple(
                    ItemConsumptionRequest(
                        item_code=objective.item_code,
                        quantity=objective.required_quantity,
                        operation_id=operation_id,
                        entry_type=ItemConsumptionType.QUEST_DELIVERY,
                        session_id=None,
                        occurred_at=occurred_at,
                    )
                    for objective in deliveries
                ),
            )
        except ItemOperationConflict as error:
            raise QuestIdempotencyConflictError() from error
        except InsufficientItemQuantity as error:
            raise QuestNotReadyError() from error

    async def _load_evaluation_context(
        self,
        uow: UnitOfWork,
        facts: CurrentLifeQuestFacts,
        objective_progresses: dict[tuple[str, str], QuestObjectiveProgress],
        *,
        lock_items: bool,
    ) -> QuestEvaluationContext:
        item_codes = {
            objective.item_code
            for quest in self._catalog.quests
            for objective in quest.objectives
            if isinstance(objective, ItemDeliveryObjectiveDefinition)
        }
        item_stacks = await uow.items.get_stacks(
            facts.life_id,
            item_codes,
            for_update=lock_items,
        )

        has_technique_objectives = any(
            isinstance(objective, TechniqueLayerObjectiveDefinition)
            for quest in self._catalog.quests
            for objective in quest.objectives
        )
        techniques = (
            await uow.cultivation.get_techniques(facts.life_id, for_update=False)
            if has_technique_objectives
            else ()
        )
        active_technique_layers = {
            technique.technique_id: technique.current_layer
            for technique in techniques
            if technique.status == "active"
        }

        has_realm_objectives = any(
            isinstance(objective, RealmLevelObjectiveDefinition)
            for quest in self._catalog.quests
            for objective in quest.objectives
        )
        current_realm_level = 1
        cultivation_revision = 0
        if has_realm_objectives or has_technique_objectives:
            cultivation_state = await uow.cultivation.get_or_create_state(
                facts.life_id,
                for_update=False,
            )
            cultivation_revision = cultivation_state.revision
            if has_realm_objectives:
                current_realm_level = cultivation_state.current_level

        return QuestEvaluationContext(
            spirit_root_present=facts.spirit_root is not None,
            item_quantities={
                item_code: stack.quantity for item_code, stack in item_stacks.items()
            },
            kill_progress={
                key: progress.current_value
                for key, progress in objective_progresses.items()
            },
            active_technique_layers=active_technique_layers,
            current_realm_level=current_realm_level,
            revision=(
                cultivation_revision
                + sum(stack.revision for stack in item_stacks.values())
            ),
        )

    def _validate_objective_progresses(
        self,
        progresses: dict[str, QuestProgress],
        objective_progresses: dict[tuple[str, str], QuestObjectiveProgress],
    ) -> None:
        expected_keys: set[tuple[str, str]] = set()
        for quest in self._catalog.quests:
            progress = progresses.get(quest.quest_id)
            if progress is None:
                continue
            for objective in quest.objectives:
                if not isinstance(objective, MythicMobKillObjectiveDefinition):
                    continue
                key = (quest.quest_id, objective.objective_id)
                expected_keys.add(key)
                stored = objective_progresses.get(key)
                if (
                    stored is None
                    or stored.life_id != progress.life_id
                    or stored.definition_version != quest.version
                    or stored.objective_type != objective.objective_type.value
                    or stored.target_id != objective.mob_internal_name
                    or stored.required_value != objective.required_count
                ):
                    raise QuestObjectiveProgressMismatchError()
        if set(objective_progresses) != expected_keys:
            raise QuestObjectiveProgressMismatchError()

    def _replay(
        self,
        operation: StoredQuestOperation,
        account_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
        fingerprint: str,
    ) -> FrozenHttpResponse:
        if (
            operation.account_id != account_id
            or operation.command is not command
            or operation.quest_id != quest_id
            or operation.provider_id != provider_id
            or operation.request_fingerprint != fingerprint
        ):
            raise QuestIdempotencyConflictError()
        if operation.state is QuestOperationState.PROCESSING:
            raise RuntimeError("Quest operation is unexpectedly still processing")
        return self._frozen_response(operation)

    @staticmethod
    def _frozen_response(operation: StoredQuestOperation) -> FrozenHttpResponse:
        if (
            operation.response_status is None
            or operation.response_content_type is None
            or operation.response_body is None
            or operation.response_contract_version is None
        ):
            raise RuntimeError("Finalized quest operation is missing response data")
        return FrozenHttpResponse(
            status_code=operation.response_status,
            content_type=operation.response_content_type,
            body=operation.response_body,
            contract_version=operation.response_contract_version,
        )

    @staticmethod
    def _fingerprint(
        account_id: UUID,
        command: QuestOperationCommand,
        quest_id: str,
        provider_id: str,
    ) -> str:
        canonical = json.dumps(
            {
                "account_id": str(account_id),
                "command": command.value,
                "contract_version": RESPONSE_CONTRACT_VERSION,
                "provider_id": provider_id,
                "quest_id": quest_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    @staticmethod
    def _check_definition_version(
        progress: QuestProgress | None,
        quest: QuestDefinition,
    ) -> None:
        if progress is not None and progress.definition_version != quest.version:
            raise QuestDefinitionVersionMismatchError()

    def _catalog_quest_ids(self) -> set[str]:
        return {quest.quest_id for quest in self._catalog.quests}

    def _validate_progress_versions(self, progresses: dict[str, QuestProgress]) -> None:
        for quest_id, progress in progresses.items():
            definition = self._catalog.find_quest(quest_id)
            if definition is None:
                raise QuestDefinitionVersionMismatchError()
            self._check_definition_version(progress, definition)

    def _build_interaction_state(
        self,
        facts: CurrentLifeQuestFacts,
        progresses: dict[str, QuestProgress],
        context: QuestEvaluationContext,
        quest_revision: int,
        provider_ids: Sequence[str],
    ) -> QuestInteractionState:
        providers = [
            self._project_provider(
                self._catalog.get_provider(provider_id),
                progresses,
                context,
            )
            for provider_id in provider_ids
        ]
        return QuestInteractionState(
            account_id=facts.account_id,
            life_id=facts.life_id,
            revision=QuestRevisionVector(
                player=facts.revision,
                quest=quest_revision,
                objectives=context.revision,
                definitions=self._catalog.revision,
            ),
            providers=providers,
            tracked_quest=self._project_tracked_quest(progresses, context),
        )

    def _project_provider(
        self,
        provider: QuestProviderDefinition,
        progresses: dict[str, QuestProgress],
        context: QuestEvaluationContext,
    ) -> QuestProviderProjection:
        provider_order = {
            quest_id: index for index, quest_id in enumerate(provider.ordered_quest_ids)
        }
        quests = [
            self._project_quest(
                self._catalog.get_quest(quest_id),
                progresses,
                context,
                provider,
            )
            for quest_id in provider.ordered_quest_ids
        ]
        quests.sort(key=lambda item: self._actionable_sort_key(item, provider_order))
        actionable = [
            quest.quest_id for quest in quests if quest.action in {"offer", "remind", "turn_in"}
        ]
        lead = next(
            (quest for quest in quests if quest.action in {"offer", "remind", "turn_in"}),
            None,
        )
        return QuestProviderProjection(
            provider_id=provider.provider_id,
            state_key=f"{lead.quest_id}:{lead.state}" if lead else f"{provider.provider_id}:none",
            quests=quests,
            actionable_quest_ids=actionable,
            direct_action_quest_id=actionable[0] if len(actionable) == 1 else None,
            proximity_bark=self._project_proximity_bark(provider, lead),
        )

    def _project_quest(
        self,
        quest: QuestDefinition,
        progresses: dict[str, QuestProgress],
        context: QuestEvaluationContext,
        provider: QuestProviderDefinition | None = None,
    ) -> ProviderQuestState:
        progress = progresses.get(quest.quest_id)
        objectives = []
        for objective in quest.objectives:
            evaluation = evaluate_objective(quest.quest_id, objective, context)
            completed = evaluation.completed
            current = evaluation.current
            if progress is not None and progress.status is QuestProgressStatus.COMPLETED:
                completed = True
                current = max(current, evaluation.required)
            objectives.append(
                QuestObjectiveProjection(
                    objective_id=objective.objective_id,
                    title=objective.label,
                    current=current,
                    required=evaluation.required,
                    completed=completed,
                )
            )
        if progress is not None and progress.status is QuestProgressStatus.COMPLETED:
            state = "completed"
        elif progress is not None and all(item.completed for item in objectives):
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
        dialogue = {
            "unavailable": None,
            "available": quest.dialogue_keys.available,
            "active": quest.dialogue_keys.active,
            "ready_to_turn_in": quest.dialogue_keys.ready_to_turn_in,
            "completed": quest.dialogue_keys.completed,
        }[state]
        return ProviderQuestState(
            quest_id=quest.quest_id,
            title=quest.title,
            category=quest.category,
            state=state,
            action=action,
            dialogue_key=dialogue if action != "none" else None,
            objectives=objectives,
        )

    def _project_tracked_quest(
        self,
        progresses: dict[str, QuestProgress],
        context: QuestEvaluationContext,
    ) -> TrackedQuest | None:
        candidates = [
            (index, quest, self._project_quest(quest, progresses, context))
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
        hint = (
            definition.presentation.ready_next_action
            if projection.state == "ready_to_turn_in"
            else definition.presentation.active_next_action
        )
        return TrackedQuest(
            quest_id=projection.quest_id,
            title=projection.title,
            state=projection.state,
            objectives=projection.objectives,
            next_action_hint=hint,
        )

    def _project_proximity_bark(
        self,
        provider: QuestProviderDefinition,
        quest: ProviderQuestState | None,
    ) -> ProximityBark | None:
        if quest is None or quest.state not in {"available", "active", "ready_to_turn_in"}:
            return None
        definition = self._catalog.get_quest(quest.quest_id)
        text = {
            "available": definition.presentation.available_proximity_text,
            "active": definition.presentation.active_proximity_text,
            "ready_to_turn_in": definition.presentation.ready_proximity_text,
        }[quest.state]
        return ProximityBark(
            key=f"{quest.quest_id}:{quest.state}",
            speaker=provider.display_name,
            text=text,
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
        is_giver = provider.provider_id in quest.provider_ids
        is_turn_in = provider.provider_id in quest.turn_in_provider_ids
        if state == "available":
            return "offer" if is_giver else "none"
        if state == "active":
            return "remind" if is_giver or is_turn_in else "none"
        if state == "ready_to_turn_in":
            return "turn_in" if is_turn_in else ("remind" if is_giver else "none")
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
        return (
            state_rank,
            0 if quest.category is QuestCategory.MAIN else 1,
            provider_order[quest.quest_id],
        )

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
        allowed = quest.turn_in_provider_ids if turn_in else quest.provider_ids
        if provider_id not in allowed or quest_id not in provider.ordered_quest_ids:
            raise QuestProviderMismatchError()
        return quest, provider
