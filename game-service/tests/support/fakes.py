import asyncio
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime
from uuid import UUID, uuid4

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
        del for_update
        return self._state.quest_revisions.setdefault(life_id, 0)

    async def increment_quest_revision(self, life_id: UUID) -> int:
        self._ensure_active()
        revision = self._state.quest_revisions.setdefault(life_id, 0) + 1
        self._state.quest_revisions[life_id] = revision
        return revision

    async def get_progresses(
        self,
        life_id: UUID,
        quest_ids: set[str],
    ) -> dict[str, QuestProgress]:
        self._ensure_active()
        return {
            quest_id: progress
            for quest_id in quest_ids
            if (progress := self._state.progresses.get((life_id, quest_id))) is not None
        }

    async def get_progress(self, life_id: UUID, quest_id: str) -> QuestProgress | None:
        self._ensure_active()
        return self._state.progresses.get((life_id, quest_id))

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


class FakeUnitOfWork:
    def __init__(self, store: FakeStore, isolation: str) -> None:
        self._store = store
        self.isolation = isolation
        self.players: FakePlayerRepository
        self.quests: FakeQuestRepository
        self._working_state: _FakeState | None = None
        self._active = False
        self._lock_held = False

    async def __aenter__(self) -> "FakeUnitOfWork":
        if self._active or self._lock_held:
            raise RuntimeError("Unit of work is already active")
        await self._store._transaction_lock.acquire()
        self._lock_held = True
        self._working_state = deepcopy(self._store._state)
        self._active = True
        self.players = FakePlayerRepository(self._working_state, self._ensure_active)
        self.quests = FakeQuestRepository(self._working_state, self._ensure_active)
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
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
