import asyncio
from collections.abc import Callable, Collection
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from types import TracebackType
from uuid import UUID, uuid4

from immortal_mmo.combat.models import CombatKillEvent
from immortal_mmo.cultivation.models import (
    CombatCultivationCredit,
    CultivationSession,
    CultivationState,
    LifeTechnique,
    RealmEntry,
    TechniqueInvestmentChange,
)
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemResourceEntry,
    ItemStack,
)
from immortal_mmo.player.models import Account, CurrentLifeQuestFacts, Life, SpiritRoot
from immortal_mmo.quest.repository import (
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
    StoredQuestOperation,
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
    combat_events: dict[UUID, CombatKillEvent] = field(default_factory=dict)
    mob_kill_counters: dict[tuple[UUID, str], int] = field(default_factory=dict)
    cultivation_balances: dict[UUID, int] = field(default_factory=dict)
    cultivation_revisions: dict[UUID, int] = field(default_factory=dict)
    cultivation_credits: dict[tuple[UUID, UUID], CombatCultivationCredit] = field(
        default_factory=dict
    )
    cultivation_states: dict[UUID, CultivationState] = field(default_factory=dict)
    life_techniques: dict[UUID, LifeTechnique] = field(default_factory=dict)
    realm_entries: dict[UUID, RealmEntry] = field(default_factory=dict)
    cultivation_sessions: dict[UUID, CultivationSession] = field(default_factory=dict)
    item_stacks: dict[tuple[UUID, str], ItemStack] = field(default_factory=dict)
    item_entries: dict[tuple[UUID, str], ItemResourceEntry] = field(default_factory=dict)


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

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        self._ensure_active()
        key = (progress.life_id, progress.quest_id)
        if key in self._state.progresses:
            return False
        self._state.progresses[key] = progress
        return True

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

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        del progress
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

    async def get_or_create_state(self, life_id: UUID, *, for_update: bool) -> CultivationState:
        self._ensure_active()
        del for_update
        return self._state.cultivation_states.setdefault(
            life_id,
            CultivationState(life_id, 1, 0, 0, None, 1),
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

    async def insert_session(self, session: CultivationSession) -> None:
        self._ensure_active()
        if any(
            stored.life_id == session.life_id and stored.status in {"pending", "active"}
            for stored in self._state.cultivation_sessions.values()
        ):
            raise RuntimeError("Active cultivation session exists")
        self._state.cultivation_sessions[session.session_id] = session

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
                technique, invested_amount=balance_after
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
        occurred_at: datetime,
    ) -> CombatCultivationCredit:
        self._ensure_active()
        del occurred_at
        key = (kill_event_id, life_id)
        if key in self._state.cultivation_credits:
            raise RuntimeError("Combat cultivation reward already exists")
        balance = self._state.cultivation_balances.get(life_id, 0) + amount
        revision = self._state.cultivation_revisions.get(life_id, 1) + 1
        credit = CombatCultivationCredit(
            entry_id=uuid4(),
            life_id=life_id,
            kill_event_id=kill_event_id,
            amount=amount,
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

    async def get_stack(self, life_id: UUID, item_code: str, *, for_update: bool) -> ItemStack:
        self._ensure_active()
        del for_update
        key = (life_id, item_code)
        return self._state.item_stacks.setdefault(key, ItemStack(life_id, item_code, 0, 1))

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
        session_id: UUID | None,
        occurred_at: datetime,
    ) -> ItemResourceEntry:
        self._ensure_active()
        replay = self._state.item_entries.get((operation_id, item_code))
        if replay is not None:
            return replay
        stack = await self.get_stack(life_id, item_code, for_update=True)
        if stack.quantity < quantity:
            raise InsufficientItemQuantity(item_code)
        balance_after = stack.quantity - quantity
        self._state.item_stacks[(life_id, item_code)] = replace(
            stack, quantity=balance_after, revision=stack.revision + 1
        )
        entry = ItemResourceEntry(
            uuid4(),
            life_id,
            item_code,
            operation_id,
            session_id,
            "breakthrough_consumption",
            -quantity,
            balance_after,
            occurred_at,
        )
        self._state.item_entries[(operation_id, item_code)] = entry
        return entry


class FakeUnitOfWork:
    def __init__(self, store: FakeStore, isolation: str) -> None:
        self._store = store
        self.isolation = isolation
        self.players: FakePlayerRepository
        self.quests: FakeQuestRepository
        self.combat: FakeCombatRepository
        self.cultivation: FakeCultivationRepository
        self.items: FakeItemRepository
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
