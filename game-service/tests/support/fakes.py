import asyncio
from collections.abc import Callable, Collection
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from immortal_mmo.combat.models import CombatKillEvent
from immortal_mmo.cultivation.layer_curves import layer_for_major_realm
from immortal_mmo.cultivation.models import (
    BreakthroughTechniqueDebit,
    CombatCultivationCredit,
    CultivationSession,
    CultivationState,
    LifeTechnique,
    QuestCultivationRewardClaim,
    QuestCultivationRewardGrant,
    RealmEntry,
    SessionTechnique,
    TechniqueInvestmentChange,
    TechniqueLearnOperation,
)
from immortal_mmo.cultivation.repository import ActiveCultivationSessionExists
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemInstance,
    ItemInstanceStatus,
    ItemLocation,
    ItemOperationConflict,
    ItemResourceEntry,
    ItemStack,
)
from immortal_mmo.player.models import Account, CurrentLifeQuestFacts, Life, SpiritRoot
from immortal_mmo.quest.repository import (
    QuestObjectiveProgress,
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
    QuestRewardGrant,
    StoredQuestOperation,
)
from immortal_mmo.storage.models import (
    StorageContainer,
    StorageOperation,
    StorageSlot,
)


@dataclass
class _FakeState:
    accounts: dict[UUID, Account] = field(default_factory=dict)
    account_ids_by_minecraft_uuid: dict[UUID, UUID] = field(default_factory=dict)
    lives: dict[UUID, Life] = field(default_factory=dict)
    spirit_roots: dict[UUID, SpiritRoot] = field(default_factory=dict)
    operations: dict[UUID, StoredQuestOperation] = field(default_factory=dict)
    quest_revisions: dict[UUID, int] = field(default_factory=dict)
    progresses: dict[tuple[UUID, str], QuestProgress] = field(default_factory=dict)
    objective_progresses: dict[tuple[UUID, str, str], QuestObjectiveProgress] = field(
        default_factory=dict
    )
    quest_reward_grants: dict[tuple[UUID, str], QuestRewardGrant] = field(
        default_factory=dict
    )
    combat_events: dict[UUID, CombatKillEvent] = field(default_factory=dict)
    mob_kill_counters: dict[tuple[UUID, str], int] = field(default_factory=dict)
    cultivation_balances: dict[UUID, int] = field(default_factory=dict)
    cultivation_revisions: dict[UUID, int] = field(default_factory=dict)
    cultivation_credits: dict[tuple[UUID, UUID], CombatCultivationCredit] = field(
        default_factory=dict
    )
    quest_cultivation_grants: dict[UUID, QuestCultivationRewardGrant] = field(
        default_factory=dict
    )
    quest_cultivation_claims: dict[UUID, QuestCultivationRewardClaim] = field(
        default_factory=dict
    )
    technique_learn_operations: dict[UUID, TechniqueLearnOperation] = field(
        default_factory=dict
    )
    cultivation_states: dict[UUID, CultivationState] = field(default_factory=dict)
    life_techniques: dict[UUID, LifeTechnique] = field(default_factory=dict)
    realm_entries: dict[UUID, RealmEntry] = field(default_factory=dict)
    cultivation_sessions: dict[UUID, CultivationSession] = field(default_factory=dict)
    session_techniques: dict[UUID, tuple[SessionTechnique, ...]] = field(default_factory=dict)
    breakthrough_debits: dict[UUID, tuple[BreakthroughTechniqueDebit, ...]] = field(
        default_factory=dict
    )
    item_stacks: dict[tuple[UUID, str], ItemStack] = field(default_factory=dict)
    item_entries: dict[tuple[UUID, str], ItemResourceEntry] = field(default_factory=dict)
    item_instances: dict[UUID, ItemInstance] = field(default_factory=dict)
    inventory_revisions: dict[UUID, int] = field(default_factory=dict)
    storage_containers: dict[tuple[UUID, str], StorageContainer] = field(
        default_factory=dict
    )
    storage_slots: dict[tuple[UUID, str, int, int], StorageSlot] = field(
        default_factory=dict
    )
    storage_operations: dict[UUID, StorageOperation] = field(default_factory=dict)


class FakeStore:
    def __init__(self) -> None:
        self._state = _FakeState()
        self._transaction_lock = asyncio.Lock()


class FakePlayerRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def upsert_account(self, minecraft_uuid: UUID, last_known_name: str) -> Account:
        self._ensure_active()
        account_id = self._state.account_ids_by_minecraft_uuid.get(minecraft_uuid)
        if account_id is None:
            account = Account(
                account_id=uuid4(),
                minecraft_uuid=minecraft_uuid,
                last_known_name=last_known_name,
                revision=1,
            )
            self._state.accounts[account.account_id] = account
            self._state.account_ids_by_minecraft_uuid[minecraft_uuid] = account.account_id
            return account
        account = self._state.accounts[account_id]
        if account.last_known_name != last_known_name:
            account = replace(
                account,
                last_known_name=last_known_name,
                revision=account.revision + 1,
            )
            self._state.accounts[account_id] = account
        return account

    async def lock_account(self, account_id: UUID) -> Account | None:
        self._ensure_active()
        return self._state.accounts.get(account_id)

    async def lock_account_by_minecraft_uuid(self, minecraft_uuid: UUID) -> Account | None:
        self._ensure_active()
        account_id = self._state.account_ids_by_minecraft_uuid.get(minecraft_uuid)
        return self._state.accounts.get(account_id) if account_id is not None else None

    async def get_current_life(self, account_id: UUID, *, for_update: bool) -> Life | None:
        self._ensure_active()
        del for_update
        return next(
            (
                life
                for life in self._state.lives.values()
                if life.account_id == account_id and life.status == "alive"
            ),
            None,
        )

    async def get_lives(self, account_id: UUID) -> tuple[Life, ...]:
        self._ensure_active()
        return tuple(
            sorted(
                (life for life in self._state.lives.values() if life.account_id == account_id),
                key=lambda life: life.generation_no,
            )
        )

    async def insert_first_life(self, account_id: UUID) -> Life:
        self._ensure_active()
        life = Life(
            life_id=uuid4(),
            account_id=account_id,
            generation_no=1,
            status="alive",
            revision=1,
        )
        self._state.lives[life.life_id] = life
        return life

    async def get_spirit_root(self, life_id: UUID) -> SpiritRoot | None:
        self._ensure_active()
        return self._state.spirit_roots.get(life_id)

    async def insert_spirit_root(self, spirit_root: SpiritRoot) -> bool:
        self._ensure_active()
        if spirit_root.life_id in self._state.spirit_roots:
            return False
        self._state.spirit_roots[spirit_root.life_id] = spirit_root
        return True

    async def increment_life_revision(self, life_id: UUID) -> int:
        self._ensure_active()
        life = self._state.lives[life_id]
        life = replace(life, revision=life.revision + 1)
        self._state.lives[life_id] = life
        return life.revision

    async def get_current_life_facts(
        self,
        account_id: UUID,
        *,
        for_update: bool,
    ) -> CurrentLifeQuestFacts | None:
        self._ensure_active()
        life = await self.get_current_life(account_id, for_update=for_update)
        if life is None:
            return None
        return CurrentLifeQuestFacts(
            account_id=account_id,
            life_id=life.life_id,
            generation_no=life.generation_no,
            spirit_root=self._state.spirit_roots.get(life.life_id),
            revision=life.revision,
        )


class FakeQuestRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def insert_reward_grant(self, grant: QuestRewardGrant) -> None:
        self._ensure_active()
        key = (grant.operation_id, grant.reward_id)
        if key in self._state.quest_reward_grants:
            raise RuntimeError("Quest reward grant already exists")
        self._state.quest_reward_grants[key] = grant

    async def get_reward_grants(
        self,
        operation_id: UUID,
    ) -> tuple[QuestRewardGrant, ...]:
        self._ensure_active()
        return tuple(
            sorted(
                (
                    grant
                    for (stored_operation_id, _), grant in self._state.quest_reward_grants.items()
                    if stored_operation_id == operation_id
                ),
                key=lambda grant: grant.reward_id,
            )
        )

    async def get_reward_grant(self, grant_id: UUID) -> QuestRewardGrant | None:
        self._ensure_active()
        return next(
            (
                grant
                for grant in self._state.quest_reward_grants.values()
                if grant.grant_id == grant_id
            ),
            None,
        )

    async def update_reward_grant_progress(
        self,
        *,
        grant_id: UUID,
        pending_amount: int,
    ) -> QuestRewardGrant:
        self._ensure_active()
        matches = [
            (key, grant)
            for key, grant in self._state.quest_reward_grants.items()
            if grant.grant_id == grant_id
        ]
        if not matches:
            raise KeyError("Quest reward grant was not found")
        key, grant = matches[0]
        updated = replace(
            grant,
            applied_amount=grant.configured_amount - pending_amount,
            pending_amount=pending_amount,
            status="applied" if pending_amount == 0 else "pending",
        )
        self._state.quest_reward_grants[key] = updated
        return updated

    async def get_operation(self, operation_id: UUID) -> StoredQuestOperation | None:
        self._ensure_active()
        return self._state.operations.get(operation_id)

    async def reserve_operation(self, operation: StoredQuestOperation) -> bool:
        self._ensure_active()
        if operation.operation_id in self._state.operations:
            return False
        self._state.operations[operation.operation_id] = operation
        return True

    async def finalize_operation(
        self,
        operation_id: UUID,
        *,
        state: QuestOperationState,
        changed: bool,
        response_status: int,
        response_content_type: str,
        response_body: bytes,
        response_contract_version: int,
        finalized_at: datetime,
    ) -> StoredQuestOperation:
        self._ensure_active()
        operation = self._state.operations[operation_id]
        if operation.state is not QuestOperationState.PROCESSING:
            raise RuntimeError("Quest operation is already finalized")
        finalized = replace(
            operation,
            state=state,
            changed=changed,
            response_status=response_status,
            response_content_type=response_content_type,
            response_body=response_body,
            response_contract_version=response_contract_version,
            finalized_at=finalized_at,
        )
        self._state.operations[operation_id] = finalized
        return finalized

    async def get_quest_revision(self, life_id: UUID, *, for_update: bool) -> int:
        self._ensure_active()
        if for_update:
            return self._state.quest_revisions.setdefault(life_id, 0)
        return self._state.quest_revisions.get(life_id, 0)

    async def increment_quest_revision(self, life_id: UUID) -> int:
        self._ensure_active()
        revision = self._state.quest_revisions.setdefault(life_id, 0) + 1
        self._state.quest_revisions[life_id] = revision
        return revision

    async def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]:
        self._ensure_active()
        return {
            quest_id: progress
            for quest_id in quest_ids
            if (progress := self._state.progresses.get((life_id, quest_id))) is not None
        }

    async def get_objective_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[tuple[str, str], QuestObjectiveProgress]:
        self._ensure_active()
        selected = set(quest_ids)
        return {
            (quest_id, objective_id): progress
            for (stored_life_id, quest_id, objective_id), progress in (
                self._state.objective_progresses.items()
            )
            if stored_life_id == life_id and quest_id in selected
        }

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        self._ensure_active()
        key = (progress.life_id, progress.quest_id)
        if key in self._state.progresses:
            return False
        self._state.progresses[key] = progress
        return True

    async def insert_objective_progresses(
        self,
        progresses: Collection[QuestObjectiveProgress],
    ) -> None:
        self._ensure_active()
        for progress in progresses:
            key = (progress.life_id, progress.quest_id, progress.objective_id)
            if key in self._state.objective_progresses:
                raise RuntimeError("Quest objective progress already exists")
            self._state.objective_progresses[key] = progress

    async def increment_objective_progress(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        objective_id: str,
        required_value: int,
        updated_at: datetime,
    ) -> int | None:
        self._ensure_active()
        key = (life_id, quest_id, objective_id)
        progress = self._state.objective_progresses.get(key)
        if (
            progress is None
            or progress.required_value != required_value
            or progress.current_value >= required_value
        ):
            return None
        current_value = min(progress.current_value + 1, required_value)
        self._state.objective_progresses[key] = replace(
            progress,
            current_value=current_value,
            updated_at=updated_at,
        )
        return current_value

    async def increment_objective_progresses(
        self,
        *,
        life_id: UUID,
        objectives: Collection[tuple[str, str]],
        updated_at: datetime,
    ) -> dict[tuple[str, str], int]:
        self._ensure_active()
        updated: dict[tuple[str, str], int] = {}
        for quest_id, objective_id in sorted(set(objectives)):
            key = (life_id, quest_id, objective_id)
            progress = self._state.objective_progresses.get(key)
            if progress is None or progress.current_value >= progress.required_value:
                continue
            current_value = min(progress.current_value + 1, progress.required_value)
            self._state.objective_progresses[key] = replace(
                progress,
                current_value=current_value,
                updated_at=updated_at,
            )
            updated[(quest_id, objective_id)] = current_value
        return updated

    async def complete_progress_if_active(
        self,
        life_id: UUID,
        quest_id: str,
        *,
        completed_at: datetime,
        revision: int,
    ) -> bool:
        self._ensure_active()
        key = (life_id, quest_id)
        progress = self._state.progresses.get(key)
        if progress is None or progress.status is not QuestProgressStatus.ACTIVE:
            return False
        self._state.progresses[key] = replace(
            progress,
            status=QuestProgressStatus.COMPLETED,
            completed_at=completed_at,
            revision=revision,
        )
        return True


class NoOpQuestRepository:
    """Task-4-only guard proving Player tests never cross into Quest persistence."""

    def __init__(self, session: object) -> None:
        del session

    @staticmethod
    def _unexpected() -> None:
        raise AssertionError("Player flow unexpectedly called the Quest repository")

    async def get_operation(self, operation_id: UUID) -> StoredQuestOperation | None:
        del operation_id
        self._unexpected()

    async def reserve_operation(self, operation: StoredQuestOperation) -> bool:
        del operation
        self._unexpected()

    async def finalize_operation(
        self,
        operation_id: UUID,
        *,
        state: QuestOperationState,
        changed: bool,
        response_status: int,
        response_content_type: str,
        response_body: bytes,
        response_contract_version: int,
        finalized_at: datetime,
    ) -> StoredQuestOperation:
        del (
            operation_id,
            state,
            changed,
            response_status,
            response_content_type,
            response_body,
            response_contract_version,
            finalized_at,
        )
        self._unexpected()

    async def get_quest_revision(self, life_id: UUID, *, for_update: bool) -> int:
        del life_id, for_update
        self._unexpected()

    async def increment_quest_revision(self, life_id: UUID) -> int:
        del life_id
        self._unexpected()

    async def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]:
        del life_id, quest_ids
        self._unexpected()

    async def get_objective_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[tuple[str, str], QuestObjectiveProgress]:
        del life_id, quest_ids
        self._unexpected()

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        del progress
        self._unexpected()

    async def insert_objective_progresses(
        self,
        progresses: Collection[QuestObjectiveProgress],
    ) -> None:
        del progresses
        self._unexpected()

    async def increment_objective_progress(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        objective_id: str,
        required_value: int,
        updated_at: datetime,
    ) -> int | None:
        del life_id, quest_id, objective_id, required_value, updated_at
        self._unexpected()

    async def increment_objective_progresses(
        self,
        *,
        life_id: UUID,
        objectives: Collection[tuple[str, str]],
        updated_at: datetime,
    ) -> dict[tuple[str, str], int]:
        del life_id, objectives, updated_at
        self._unexpected()

    async def complete_progress_if_active(
        self,
        life_id: UUID,
        quest_id: str,
        *,
        completed_at: datetime,
        revision: int,
    ) -> bool:
        del life_id, quest_id, completed_at, revision
        self._unexpected()


class FakeCombatRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def get_event(self, source_event_id: UUID) -> CombatKillEvent | None:
        self._ensure_active()
        return self._state.combat_events.get(source_event_id)

    async def insert_event_if_absent(self, event: CombatKillEvent) -> bool:
        self._ensure_active()
        if event.source_event_id in self._state.combat_events:
            return False
        self._state.combat_events[event.source_event_id] = event
        return True

    async def finalize_reward_result(
        self,
        kill_event_id: UUID,
        *,
        credited_cultivation_amount: int,
        unrefined_balance_after: int,
    ) -> None:
        self._ensure_active()
        for source_event_id, event in self._state.combat_events.items():
            if event.kill_event_id == kill_event_id:
                self._state.combat_events[source_event_id] = replace(
                    event,
                    credited_cultivation_amount=credited_cultivation_amount,
                    unrefined_balance_after=unrefined_balance_after,
                )
                return
        raise RuntimeError("Combat reward event disappeared before finalization")

    async def increment_mob_counter(
        self,
        life_id: UUID,
        mob_internal_name: str,
        occurred_at: datetime,
    ) -> int:
        self._ensure_active()
        del occurred_at
        key = (life_id, mob_internal_name)
        count = self._state.mob_kill_counters.get(key, 0) + 1
        self._state.mob_kill_counters[key] = count
        return count

    async def get_mob_counter(self, life_id: UUID, mob_internal_name: str) -> int:
        self._ensure_active()
        return self._state.mob_kill_counters.get((life_id, mob_internal_name), 0)


class FakeCultivationRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def claim_pending_quest_reward(
        self,
        *,
        operation_id: UUID,
        grant_id: UUID,
        life_id: UUID,
        cap: int,
        occurred_at: datetime,
    ) -> QuestCultivationRewardClaim:
        self._ensure_active()
        replay = self._state.quest_cultivation_claims.get(operation_id)
        if replay is not None:
            return replay
        grant = self._state.quest_cultivation_grants.get(grant_id)
        if grant is None or grant.life_id != life_id:
            raise KeyError("Pending quest cultivation reward was not found")
        if grant.pending_amount == 0:
            raise ValueError("Quest cultivation reward is already fully applied")
        state = await self.get_or_create_state(life_id, for_update=True)
        applied = min(grant.pending_amount, max(cap - state.unrefined_cultivation, 0))
        if applied == 0:
            raise ValueError("Unrefined cultivation reserve is full")
        pending = grant.pending_amount - applied
        balance = state.unrefined_cultivation + applied
        self._state.cultivation_states[life_id] = replace(
            state,
            unrefined_cultivation=balance,
            revision=state.revision + 1,
        )
        self._state.quest_cultivation_grants[grant_id] = replace(
            grant,
            credited_amount=grant.credited_amount + applied,
            pending_amount=pending,
            balance_after=balance,
            status="applied" if pending == 0 else "pending",
        )
        claim = QuestCultivationRewardClaim(
            operation_id=operation_id,
            grant_id=grant_id,
            life_id=life_id,
            applied_amount=applied,
            pending_amount=pending,
            balance_after=balance,
            response_body=None,
            created_at=occurred_at,
        )
        self._state.quest_cultivation_claims[operation_id] = claim
        return claim

    async def finalize_quest_reward_claim(
        self,
        *,
        operation_id: UUID,
        response_body: bytes,
    ) -> QuestCultivationRewardClaim:
        self._ensure_active()
        claim = self._state.quest_cultivation_claims[operation_id]
        finalized = replace(claim, response_body=response_body)
        self._state.quest_cultivation_claims[operation_id] = finalized
        return finalized

    async def get_learn_operation(
        self,
        operation_id: UUID,
    ) -> TechniqueLearnOperation | None:
        self._ensure_active()
        return self._state.technique_learn_operations.get(operation_id)

    async def learn_technique(
        self,
        *,
        operation: TechniqueLearnOperation,
        technique: LifeTechnique,
    ) -> LifeTechnique:
        self._ensure_active()
        if operation.operation_id in self._state.technique_learn_operations:
            raise RuntimeError("Technique learn operation already exists")
        if any(
            item.life_id == technique.life_id and item.technique_id == technique.technique_id
            for item in self._state.life_techniques.values()
        ):
            raise ValueError("Technique is already known")
        self._state.technique_learn_operations[operation.operation_id] = operation
        self._state.life_techniques[technique.life_technique_id] = technique
        state = await self.get_or_create_state(technique.life_id, for_update=True)
        self._state.cultivation_states[technique.life_id] = replace(
            state,
            revision=state.revision + 1,
        )
        return technique

    async def finalize_learn_operation(
        self,
        *,
        operation_id: UUID,
        response_body: bytes,
    ) -> TechniqueLearnOperation:
        self._ensure_active()
        operation = self._state.technique_learn_operations[operation_id]
        finalized = replace(operation, response_body=response_body)
        self._state.technique_learn_operations[operation_id] = finalized
        return finalized

    async def grant_quest_reward(
        self,
        *,
        grant_id: UUID,
        life_id: UUID,
        operation_id: UUID,
        quest_id: str,
        reward_id: str,
        configured_amount: int,
        cap: int,
        occurred_at: datetime,
    ) -> QuestCultivationRewardGrant:
        self._ensure_active()
        existing = self._state.quest_cultivation_grants.get(grant_id)
        if existing is not None:
            return existing
        state = await self.get_or_create_state(life_id, for_update=True)
        credited = min(configured_amount, max(cap - state.unrefined_cultivation, 0))
        pending = configured_amount - credited
        updated = replace(
            state,
            unrefined_cultivation=state.unrefined_cultivation + credited,
            revision=state.revision + (1 if credited else 0),
        )
        self._state.cultivation_states[life_id] = updated
        grant = QuestCultivationRewardGrant(
            grant_id=grant_id,
            life_id=life_id,
            operation_id=operation_id,
            quest_id=quest_id,
            reward_id=reward_id,
            configured_amount=configured_amount,
            credited_amount=credited,
            pending_amount=pending,
            balance_after=updated.unrefined_cultivation,
            status="applied" if pending == 0 else "pending",
        )
        self._state.quest_cultivation_grants[grant_id] = grant
        return grant

    async def get_or_create_state(self, life_id: UUID, *, for_update: bool) -> CultivationState:
        self._ensure_active()
        del for_update
        return self._state.cultivation_states.setdefault(
            life_id,
            CultivationState(life_id, 0, 0, 0, None, 1),
        )

    async def get_techniques(
        self,
        life_id: UUID,
        technique_ids: Collection[UUID] = (),
        *,
        for_update: bool,
    ) -> tuple[LifeTechnique, ...]:
        self._ensure_active()
        del for_update
        selected = set(technique_ids)
        return tuple(
            sorted(
                (
                    technique
                    for technique in self._state.life_techniques.values()
                    if technique.life_id == life_id
                    and (not selected or technique.life_technique_id in selected)
                ),
                key=lambda technique: technique.life_technique_id.int,
            )
        )

    async def get_active_realm_chain(
        self, life_id: UUID, *, for_update: bool
    ) -> tuple[RealmEntry, ...]:
        self._ensure_active()
        del for_update
        return tuple(
            sorted(
                (
                    entry
                    for entry in self._state.realm_entries.values()
                    if entry.life_id == life_id and entry.status == "active"
                ),
                key=lambda entry: entry.generation,
            )
        )

    async def get_group_investments(self, life_id: UUID) -> dict[str, int]:
        self._ensure_active()
        totals: dict[str, int] = {}
        for technique in self._state.life_techniques.values():
            if technique.life_id == life_id and technique.status == "active":
                totals[technique.group_code] = (
                    totals.get(technique.group_code, 0) + technique.invested_amount
                )
        return totals

    async def get_latest_realm_generation(self, life_id: UUID) -> int:
        self._ensure_active()
        return max(
            (
                entry.generation
                for entry in self._state.realm_entries.values()
                if entry.life_id == life_id
            ),
            default=0,
        )

    async def has_realm_transition_history(
        self,
        life_id: UUID,
        *,
        source_level: int,
        target_level: int,
    ) -> bool:
        self._ensure_active()
        return any(
            entry.life_id == life_id
            and entry.source_level == source_level
            and entry.target_level == target_level
            for entry in self._state.realm_entries.values()
        )

    async def append_realm_entry(self, entry: RealmEntry) -> CultivationState:
        self._ensure_active()
        self._state.realm_entries[entry.realm_entry_id] = entry
        state = await self.get_or_create_state(entry.life_id, for_update=True)
        updated = replace(
            state,
            current_level=entry.target_level,
            revision=state.revision + 1,
        )
        self._state.cultivation_states[entry.life_id] = updated
        return updated

    async def invalidate_realm_suffix(
        self,
        *,
        life_id: UUID,
        retained_entry_ids: tuple[UUID, ...],
        current_level: int,
        invalidated_at: datetime,
    ) -> CultivationState:
        self._ensure_active()
        retained = set(retained_entry_ids)
        for entry_id, entry in tuple(self._state.realm_entries.items()):
            if entry.life_id != life_id or entry.status != "active" or entry_id in retained:
                continue
            self._state.realm_entries[entry_id] = replace(
                entry,
                status="invalidated",
                invalidated_at=invalidated_at,
            )
        state = await self.get_or_create_state(life_id, for_update=True)
        updated = replace(
            state,
            current_level=current_level,
            revision=state.revision + 1,
        )
        self._state.cultivation_states[life_id] = updated
        return updated

    async def abandon_technique(
        self,
        *,
        life_id: UUID,
        life_technique_id: UUID,
    ) -> CultivationState:
        self._ensure_active()
        technique = self._state.life_techniques[life_technique_id]
        if technique.life_id != life_id or technique.status != "active":
            raise KeyError("Unknown active life technique")
        self._state.life_techniques[life_technique_id] = replace(
            technique,
            status="abandoned",
        )
        state = await self.get_or_create_state(life_id, for_update=True)
        updated = replace(state, revision=state.revision + 1)
        self._state.cultivation_states[life_id] = updated
        return updated

    async def insert_session(self, session: CultivationSession) -> None:
        self._ensure_active()
        if any(
            stored.life_id == session.life_id and stored.status in {"pending", "active"}
            for stored in self._state.cultivation_sessions.values()
        ):
            raise ActiveCultivationSessionExists(session.life_id)
        self._state.cultivation_sessions[session.session_id] = session

    async def start_session(
        self,
        session: CultivationSession,
        techniques: tuple[SessionTechnique, ...],
    ) -> None:
        await self.insert_session(session)
        self._state.session_techniques[session.session_id] = techniques
        state = await self.get_or_create_state(session.life_id, for_update=True)
        self._state.cultivation_states[session.life_id] = replace(
            state,
            active_session_id=session.session_id,
            revision=state.revision + 1,
        )

    async def get_session(self, session_id: UUID, *, for_update: bool) -> CultivationSession | None:
        self._ensure_active()
        del for_update
        return self._state.cultivation_sessions.get(session_id)

    async def get_session_by_idempotency(
        self, life_id: UUID, idempotency_key: UUID
    ) -> CultivationSession | None:
        self._ensure_active()
        return next(
            (
                session
                for session in self._state.cultivation_sessions.values()
                if session.life_id == life_id and session.idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_session_techniques(self, session_id: UUID) -> tuple[SessionTechnique, ...]:
        self._ensure_active()
        return self._state.session_techniques.get(session_id, ())

    async def store_breakthrough_debits(
        self,
        debits: tuple[BreakthroughTechniqueDebit, ...],
    ) -> None:
        self._ensure_active()
        if debits:
            self._state.breakthrough_debits[debits[0].session_id] = debits

    async def get_breakthrough_debits(
        self, session_id: UUID
    ) -> tuple[BreakthroughTechniqueDebit, ...]:
        self._ensure_active()
        return self._state.breakthrough_debits.get(session_id, ())

    async def update_session_frozen_snapshot(
        self,
        *,
        session_id: UUID,
        frozen_snapshot: dict[str, object],
    ) -> CultivationSession:
        self._ensure_active()
        session = self._state.cultivation_sessions[session_id]
        updated = replace(
            session,
            frozen_snapshot=frozen_snapshot,
            revision=session.revision + 1,
        )
        self._state.cultivation_sessions[session_id] = updated
        return updated

    async def consume_unrefined(
        self,
        *,
        life_id: UUID,
        session_id: UUID,
        operation_id: UUID,
        amount: int,
        occurred_at: datetime,
    ) -> CultivationState:
        self._ensure_active()
        del session_id, operation_id, occurred_at
        state = await self.get_or_create_state(life_id, for_update=True)
        if state.unrefined_cultivation < amount:
            raise ValueError("Insufficient unrefined cultivation")
        updated = replace(
            state,
            unrefined_cultivation=state.unrefined_cultivation - amount,
            revision=state.revision + 1,
        )
        self._state.cultivation_states[life_id] = updated
        self._state.cultivation_balances[life_id] = updated.unrefined_cultivation
        return updated

    async def update_session_settlement(
        self,
        *,
        session_id: UUID,
        cumulative_elapsed_seconds: int,
        cumulative_generated: int,
        cumulative_reserve_consumed: int,
        cumulative_retained: int,
        status: str,
        settled_at: datetime | None,
    ) -> CultivationSession:
        self._ensure_active()
        session = self._state.cultivation_sessions[session_id]
        updated = replace(
            session,
            cumulative_elapsed_seconds=cumulative_elapsed_seconds,
            cumulative_generated=cumulative_generated,
            cumulative_reserve_consumed=cumulative_reserve_consumed,
            cumulative_retained=cumulative_retained,
            status=status,
            settled_at=settled_at,
            revision=session.revision + 1,
        )
        self._state.cultivation_sessions[session_id] = updated
        if status in {"completed", "failed", "cancelled"}:
            state = self._state.cultivation_states[session.life_id]
            self._state.cultivation_states[session.life_id] = replace(
                state, active_session_id=None, revision=state.revision + 1
            )
        return updated

    async def apply_technique_investments(
        self,
        *,
        life_id: UUID,
        operation_id: UUID,
        session_id: UUID | None,
        changes: tuple[TechniqueInvestmentChange, ...],
        occurred_at: datetime,
    ) -> CultivationState:
        self._ensure_active()
        del operation_id, session_id, occurred_at
        state = await self.get_or_create_state(life_id, for_update=True)
        total_delta = 0
        for change in changes:
            technique = self._state.life_techniques[change.life_technique_id]
            balance_after = technique.invested_amount + change.delta_amount
            if not 0 <= balance_after <= technique.max_investment:
                raise ValueError("Technique investment exceeds its bounds")
            self._state.life_techniques[change.life_technique_id] = replace(
                technique,
                invested_amount=balance_after,
                current_layer=layer_for_major_realm(
                    balance_after,
                    technique.max_investment,
                    technique.major_realm,
                ),
            )
            total_delta += change.delta_amount
        updated = replace(
            state,
            realized_cultivation=state.realized_cultivation + total_delta,
            revision=state.revision + 1,
        )
        self._state.cultivation_states[life_id] = updated
        return updated

    async def get_combat_credit(
        self,
        kill_event_id: UUID,
        life_id: UUID,
    ) -> CombatCultivationCredit | None:
        self._ensure_active()
        return self._state.cultivation_credits.get((kill_event_id, life_id))

    async def credit_combat_reward(
        self,
        *,
        life_id: UUID,
        kill_event_id: UUID,
        amount: int,
        cap: int,
        occurred_at: datetime,
    ) -> CombatCultivationCredit:
        self._ensure_active()
        del occurred_at
        key = (kill_event_id, life_id)
        if key in self._state.cultivation_credits:
            raise RuntimeError("Combat cultivation reward already exists")
        current = self._state.cultivation_balances.get(life_id, 0)
        credited = min(amount, max(cap - current, 0))
        balance = current + credited
        revision = self._state.cultivation_revisions.get(life_id, 1) + 1
        credit = CombatCultivationCredit(
            entry_id=uuid4() if credited > 0 else None,
            life_id=life_id,
            kill_event_id=kill_event_id,
            amount=credited,
            balance_after=balance,
            revision=revision,
        )
        self._state.cultivation_balances[life_id] = balance
        self._state.cultivation_revisions[life_id] = revision
        self._state.cultivation_credits[key] = credit
        state = await self.get_or_create_state(life_id, for_update=True)
        self._state.cultivation_states[life_id] = replace(
            state,
            unrefined_cultivation=balance,
            revision=revision,
        )
        return credit

    async def get_unrefined_balance(self, life_id: UUID) -> int:
        self._ensure_active()
        return self._state.cultivation_balances.get(life_id, 0)


class FakeItemRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def get_inventory_revision(self, life_id: UUID, *, for_update: bool) -> int:
        self._ensure_active()
        del for_update
        return self._state.inventory_revisions.get(life_id, 0)

    async def get_pending_instances(self, life_id: UUID) -> tuple[ItemInstance, ...]:
        self._ensure_active()
        return tuple(
            sorted(
                (
                    item
                    for item in self._state.item_instances.values()
                    if item.life_id == life_id
                    and item.status is ItemInstanceStatus.PENDING_DELIVERY
                ),
                key=lambda item: (item.created_at, item.item_instance_id.int),
            )
        )

    async def count_pending_quest_reward_instances(
        self,
        quest_reward_grant_id: UUID,
    ) -> int:
        self._ensure_active()
        return sum(
            item.quest_reward_grant_id == quest_reward_grant_id
            and item.status is ItemInstanceStatus.PENDING_DELIVERY
            for item in self._state.item_instances.values()
        )

    async def create_pending_instances(
        self,
        *,
        life_id: UUID,
        issuance_id: UUID,
        quest_reward_grant_id: UUID | None,
        item_code: str,
        definition_version: int,
        technique_id: str | None,
        item_instance_ids: Collection[UUID],
        created_at: datetime,
    ) -> tuple[ItemInstance, ...]:
        self._ensure_active()
        result: list[ItemInstance] = []
        for ordinal, item_instance_id in enumerate(item_instance_ids):
            existing = self._state.item_instances.get(item_instance_id)
            if existing is not None:
                if (
                    existing.life_id != life_id
                    or existing.issuance_id != issuance_id
                    or existing.issuance_ordinal != ordinal
                    or existing.quest_reward_grant_id != quest_reward_grant_id
                    or existing.item_code != item_code
                ):
                    raise ItemOperationConflict
                result.append(existing)
                continue
            instance = ItemInstance(
                item_instance_id=item_instance_id,
                life_id=life_id,
                item_code=item_code,
                definition_version=definition_version,
                technique_id=technique_id,
                issuance_id=issuance_id,
                issuance_ordinal=ordinal,
                quest_reward_grant_id=quest_reward_grant_id,
                status=ItemInstanceStatus.PENDING_DELIVERY,
                created_at=created_at,
                delivered_at=None,
                consumed_at=None,
            )
            self._state.item_instances[item_instance_id] = instance
            result.append(instance)
        return tuple(result)

    async def get_instance(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> ItemInstance | None:
        self._ensure_active()
        del for_update
        return self._state.item_instances.get(item_instance_id)

    async def get_instances(
        self,
        item_instance_ids: Collection[UUID],
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]:
        self._ensure_active()
        del for_update
        identities = tuple(sorted(set(item_instance_ids)))
        return tuple(
            self._state.item_instances[item_id]
            for item_id in identities
            if item_id in self._state.item_instances
        )

    async def confirm_delivery(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        delivered_at: datetime,
    ) -> ItemInstance:
        self._ensure_active()
        instance = self._state.item_instances.get(item_instance_id)
        if instance is None or instance.life_id != life_id:
            raise KeyError("Item instance was not found for current life")
        if instance.status in {
            ItemInstanceStatus.OWNED,
            ItemInstanceStatus.CONSUMED,
        }:
            return instance
        updated = replace(
            instance,
            status=ItemInstanceStatus.OWNED,
            location=ItemLocation.INVENTORY,
            delivered_at=delivered_at,
        )
        self._state.item_instances[item_instance_id] = updated
        self._increment_inventory_revision(life_id)
        return updated

    async def consume_instance(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        consumed_at: datetime,
    ) -> ItemInstance:
        self._ensure_active()
        instance = self._state.item_instances.get(item_instance_id)
        if instance is None or instance.life_id != life_id:
            raise KeyError("Item instance was not found for current life")
        if instance.status is ItemInstanceStatus.CONSUMED:
            return instance
        if instance.status not in {
            ItemInstanceStatus.PENDING_DELIVERY,
            ItemInstanceStatus.OWNED,
        }:
            raise ItemOperationConflict
        consumed = replace(
            instance,
            status=ItemInstanceStatus.CONSUMED,
            location=None,
            consumed_at=consumed_at,
        )
        self._state.item_instances[item_instance_id] = consumed
        self._increment_inventory_revision(life_id)
        return consumed

    async def consume_inventory_instances(
        self,
        *,
        life_id: UUID,
        item_instance_ids: Collection[UUID],
        consumed_at: datetime,
    ) -> tuple[ItemInstance, ...]:
        self._ensure_active()
        identities = tuple(dict.fromkeys(item_instance_ids))
        if not identities:
            return ()
        instances = await self.get_instances(identities, for_update=True)
        by_id = {item.item_instance_id: item for item in instances}
        if len(by_id) != len(identities):
            raise KeyError("One or more item instances were not found")
        if any(
            item.life_id != life_id
            or item.status is not ItemInstanceStatus.OWNED
            or item.location is not ItemLocation.INVENTORY
            for item in instances
        ):
            raise ItemOperationConflict("One or more item instances are not in inventory")
        result = []
        for item_id in identities:
            consumed = replace(
                by_id[item_id],
                status=ItemInstanceStatus.CONSUMED,
                location=None,
                consumed_at=consumed_at,
            )
            self._state.item_instances[item_id] = consumed
            result.append(consumed)
        self._increment_inventory_revision(life_id)
        return tuple(result)

    async def get_inventory_instances(
        self,
        life_id: UUID,
        item_codes: Collection[str] = (),
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]:
        self._ensure_active()
        del for_update
        allowed = set(item_codes)
        return tuple(
            sorted(
                (
                    item
                    for item in self._state.item_instances.values()
                    if item.life_id == life_id
                    and item.status is ItemInstanceStatus.OWNED
                    and item.location is ItemLocation.INVENTORY
                    and (not allowed or item.item_code in allowed)
                ),
                key=lambda item: (item.item_code, item.item_instance_id),
            )
        )

    async def set_instance_location(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        expected: ItemLocation,
        destination: ItemLocation,
    ) -> ItemInstance:
        self._ensure_active()
        item = self._state.item_instances.get(item_instance_id)
        if (
            item is None
            or item.life_id != life_id
            or item.status is not ItemInstanceStatus.OWNED
            or item.location is not expected
        ):
            raise ItemOperationConflict("Item instance location changed")
        updated = replace(item, location=destination)
        self._state.item_instances[item_instance_id] = updated
        self._increment_inventory_revision(life_id)
        return updated

    def _increment_inventory_revision(self, life_id: UUID) -> int:
        revision = self._state.inventory_revisions.get(life_id, 0) + 1
        self._state.inventory_revisions[life_id] = revision
        return revision

    async def get_stack(self, life_id: UUID, item_code: str, *, for_update: bool) -> ItemStack:
        self._ensure_active()
        del for_update
        key = (life_id, item_code)
        return self._state.item_stacks.setdefault(key, ItemStack(life_id, item_code, 0, 1))

    async def get_stacks(
        self,
        life_id: UUID,
        item_codes: Collection[str],
        *,
        for_update: bool,
    ) -> dict[str, ItemStack]:
        self._ensure_active()
        del for_update
        return {
            item_code: self._state.item_stacks.get(
                (life_id, item_code),
                ItemStack(life_id, item_code, 0, 1),
            )
            for item_code in sorted(set(item_codes))
        }

    async def adjust(
        self,
        *,
        life_id: UUID,
        item_code: str,
        delta_quantity: int,
        operation_id: UUID,
        occurred_at: datetime,
    ) -> ItemResourceEntry:
        self._ensure_active()
        replay = self._state.item_entries.get((operation_id, item_code))
        if replay is not None:
            if (
                replay.life_id != life_id
                or replay.session_id is not None
                or replay.entry_type != "administrative_adjustment"
                or replay.delta_quantity != delta_quantity
            ):
                raise ItemOperationConflict
            return replay
        stack = await self.get_stack(life_id, item_code, for_update=True)
        balance_after = stack.quantity + delta_quantity
        if balance_after < 0:
            raise InsufficientItemQuantity(item_code)
        self._state.item_stacks[(life_id, item_code)] = replace(
            stack, quantity=balance_after, revision=stack.revision + 1
        )
        entry = ItemResourceEntry(
            uuid4(),
            life_id,
            item_code,
            operation_id,
            None,
            "administrative_adjustment",
            delta_quantity,
            balance_after,
            occurred_at,
        )
        self._state.item_entries[(operation_id, item_code)] = entry
        return entry

    async def consume(
        self,
        *,
        life_id: UUID,
        item_code: str,
        quantity: int,
        operation_id: UUID,
        entry_type: ItemConsumptionType,
        session_id: UUID | None,
        occurred_at: datetime,
    ) -> ItemResourceEntry:
        entries = await self.consume_many(
            life_id=life_id,
            consumptions=(
                ItemConsumptionRequest(
                    item_code=item_code,
                    quantity=quantity,
                    operation_id=operation_id,
                    entry_type=entry_type,
                    session_id=session_id,
                    occurred_at=occurred_at,
                ),
            ),
        )
        return entries[0]

    async def consume_many(
        self,
        *,
        life_id: UUID,
        consumptions: Collection[ItemConsumptionRequest],
    ) -> tuple[ItemResourceEntry, ...]:
        self._ensure_active()
        requests = tuple(consumptions)
        if not requests:
            return ()
        if len({request.item_code for request in requests}) != len(requests):
            raise ValueError("Item consumption item codes must be unique")
        for request in requests:
            _validate_fake_consumption_request(request)
        replays: dict[tuple[UUID, str], ItemResourceEntry] = {}
        for request in requests:
            replay = self._state.item_entries.get((request.operation_id, request.item_code))
            if replay is not None:
                _validate_fake_replay(life_id, request, replay)
                replays[(request.operation_id, request.item_code)] = replay
        new_requests = tuple(
            request
            for request in requests
            if (request.operation_id, request.item_code) not in replays
        )
        stacks = {
            request.item_code: await self.get_stack(
                life_id, request.item_code, for_update=True
            )
            for request in new_requests
        }
        for request in new_requests:
            if stacks[request.item_code].quantity < request.quantity:
                raise InsufficientItemQuantity(request.item_code)
        for request in new_requests:
            stack = stacks[request.item_code]
            balance_after = stack.quantity - request.quantity
            updated_stack = replace(stack, quantity=balance_after, revision=stack.revision + 1)
            self._state.item_stacks[(life_id, request.item_code)] = updated_stack
            entry = ItemResourceEntry(
                uuid4(),
                life_id,
                request.item_code,
                request.operation_id,
                request.session_id,
                request.entry_type.value,
                -request.quantity,
                balance_after,
                request.occurred_at,
            )
            self._state.item_entries[(request.operation_id, request.item_code)] = entry
            replays[(request.operation_id, request.item_code)] = entry
        return tuple(
            replays[(request.operation_id, request.item_code)] for request in requests
        )


def _validate_fake_consumption_request(request: ItemConsumptionRequest) -> None:
    if request.quantity <= 0:
        raise ValueError("Consumed item quantity must be positive")
    if (
        request.entry_type is ItemConsumptionType.BREAKTHROUGH
        and request.session_id is None
    ):
        raise ValueError("Breakthrough consumption requires a session ID")


def _validate_fake_replay(
    life_id: UUID,
    request: ItemConsumptionRequest,
    replay: ItemResourceEntry,
) -> None:
    if (
        replay.life_id != life_id
        or replay.session_id != request.session_id
        or replay.entry_type != request.entry_type.value
        or replay.delta_quantity != -request.quantity
    ):
        raise ItemOperationConflict


class FakeStorageRepository:
    def __init__(self, state: _FakeState, ensure_active: Callable[[], None]) -> None:
        self._state = state
        self._ensure_active = ensure_active

    async def lock_operation(self, operation_id: UUID) -> None:
        del operation_id
        self._ensure_active()

    async def get_container(
        self,
        life_id: UUID,
        area_id: str,
        *,
        for_update: bool,
    ) -> StorageContainer | None:
        self._ensure_active()
        del for_update
        return self._state.storage_containers.get((life_id, area_id))

    async def create_container(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page_count: int,
        item_slots_per_page: int,
    ) -> StorageContainer:
        self._ensure_active()
        key = (life_id, area_id)
        container = self._state.storage_containers.get(key)
        if container is None:
            now = datetime.now(UTC)
            container = StorageContainer(
                life_id=life_id,
                area_id=area_id,
                page_count=page_count,
                item_slots_per_page=item_slots_per_page,
                revision=0,
                created_at=now,
                updated_at=now,
            )
            self._state.storage_containers[key] = container
        if (
            container.page_count != page_count
            or container.item_slots_per_page != item_slots_per_page
        ):
            raise RuntimeError("Storage container shape differs from current catalog")
        return container

    async def get_page_slots(
        self,
        life_id: UUID,
        area_id: str,
        page: int,
    ) -> tuple[StorageSlot, ...]:
        self._ensure_active()
        return tuple(
            sorted(
                (
                    slot
                    for slot in self._state.storage_slots.values()
                    if slot.life_id == life_id
                    and slot.area_id == area_id
                    and slot.page == page
                ),
                key=lambda value: value.slot,
            )
        )

    async def get_slots(
        self,
        life_id: UUID,
        area_id: str,
        positions: Collection[tuple[int, int]],
        *,
        for_update: bool,
    ) -> dict[tuple[int, int], StorageSlot]:
        self._ensure_active()
        del for_update
        return {
            (page, slot): stored
            for page, slot in sorted(set(positions))
            if (
                stored := self._state.storage_slots.get(
                    (life_id, area_id, page, slot)
                )
            )
            is not None
        }

    async def find_item_slot(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> StorageSlot | None:
        self._ensure_active()
        del for_update
        return next(
            (
                slot
                for slot in self._state.storage_slots.values()
                if slot.item_instance_id == item_instance_id
            ),
            None,
        )

    async def put_slot(self, slot: StorageSlot) -> None:
        self._ensure_active()
        key = (slot.life_id, slot.area_id, slot.page, slot.slot)
        if key in self._state.storage_slots:
            raise RuntimeError("Storage slot is occupied")
        if await self.find_item_slot(slot.item_instance_id, for_update=True) is not None:
            raise RuntimeError("Item already occupies a storage slot")
        self._state.storage_slots[key] = slot

    async def delete_slot(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page: int,
        slot: int,
        item_instance_id: UUID,
    ) -> None:
        self._ensure_active()
        key = (life_id, area_id, page, slot)
        stored = self._state.storage_slots.get(key)
        if stored is None or stored.item_instance_id != item_instance_id:
            raise RuntimeError("Storage slot changed before removal")
        del self._state.storage_slots[key]

    async def move_slot(
        self,
        *,
        life_id: UUID,
        area_id: str,
        source_page: int,
        source_slot: int,
        destination_page: int,
        destination_slot: int,
        item_instance_id: UUID,
    ) -> None:
        self._ensure_active()
        source_key = (life_id, area_id, source_page, source_slot)
        destination_key = (life_id, area_id, destination_page, destination_slot)
        source = self._state.storage_slots.get(source_key)
        if source is None or source.item_instance_id != item_instance_id:
            raise RuntimeError("Storage source slot changed before move")
        if destination_key in self._state.storage_slots:
            raise RuntimeError("Storage destination slot is occupied")
        del self._state.storage_slots[source_key]
        self._state.storage_slots[destination_key] = replace(
            source,
            page=destination_page,
            slot=destination_slot,
            updated_at=datetime.now(UTC),
        )

    async def increment_revision(
        self,
        *,
        life_id: UUID,
        area_id: str,
        expected_revision: int,
    ) -> int:
        self._ensure_active()
        key = (life_id, area_id)
        container = self._state.storage_containers[key]
        if container.revision != expected_revision:
            raise RuntimeError("Storage revision changed before mutation")
        container = replace(
            container,
            revision=container.revision + 1,
            updated_at=datetime.now(UTC),
        )
        self._state.storage_containers[key] = container
        return container.revision

    async def get_operation(self, operation_id: UUID) -> StorageOperation | None:
        self._ensure_active()
        return self._state.storage_operations.get(operation_id)

    async def insert_operation(self, operation: StorageOperation) -> None:
        self._ensure_active()
        if operation.operation_id in self._state.storage_operations:
            raise RuntimeError("Storage operation already exists")
        self._state.storage_operations[operation.operation_id] = operation


class FakeUnitOfWork:
    def __init__(self, store: FakeStore, isolation: str) -> None:
        self._store = store
        self.isolation = isolation
        self.players: FakePlayerRepository
        self.quests: FakeQuestRepository
        self.combat: FakeCombatRepository
        self.cultivation: FakeCultivationRepository
        self.items: FakeItemRepository
        self.storage: FakeStorageRepository
        self._working_state: _FakeState | None = None
        self._entered = False
        self._active = False
        self._lock_held = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        if self._entered:
            raise RuntimeError("Unit of work was already entered")
        self._entered = True
        await self._store._transaction_lock.acquire()
        self._lock_held = True
        self._working_state = deepcopy(self._store._state)
        self._active = True
        self.players = FakePlayerRepository(self._working_state, self._ensure_active)
        self.quests = FakeQuestRepository(self._working_state, self._ensure_active)
        self.combat = FakeCombatRepository(self._working_state, self._ensure_active)
        self.cultivation = FakeCultivationRepository(self._working_state, self._ensure_active)
        self.items = FakeItemRepository(self._working_state, self._ensure_active)
        self.storage = FakeStorageRepository(self._working_state, self._ensure_active)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        if self._active:
            await self.rollback()

    async def commit(self) -> None:
        self._ensure_active()
        assert self._working_state is not None
        self._store._state = deepcopy(self._working_state)
        self._close()

    async def rollback(self) -> None:
        self._ensure_active()
        self._close()

    def _ensure_active(self) -> None:
        if not self._active or self._working_state is None:
            raise RuntimeError("Unit of work is closed")

    def _close(self) -> None:
        self._active = False
        self._working_state = None
        if self._lock_held:
            self._lock_held = False
            self._store._transaction_lock.release()


class FakeUnitOfWorkFactory:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.isolations: list[str] = []

    def __call__(self, *, isolation: str = "read_committed") -> FakeUnitOfWork:
        self.isolations.append(isolation)
        return FakeUnitOfWork(self.store, isolation)


def processing_operation(
    *,
    operation_id: UUID,
    account_id: UUID,
    life_id: UUID,
    command: QuestOperationCommand,
    quest_id: str,
    provider_id: str,
    request_fingerprint: str,
    created_at: datetime | None = None,
) -> StoredQuestOperation:
    return StoredQuestOperation(
        operation_id=operation_id,
        account_id=account_id,
        life_id=life_id,
        command=command,
        quest_id=quest_id,
        provider_id=provider_id,
        request_fingerprint=request_fingerprint,
        state=QuestOperationState.PROCESSING,
        changed=None,
        response_status=None,
        response_content_type=None,
        response_body=None,
        response_contract_version=None,
        created_at=created_at or datetime.now().astimezone(),
        finalized_at=None,
    )
