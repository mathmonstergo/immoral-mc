from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.quest.db_models import (
    LifeQuestStateRow,
    QuestOperationRow,
    QuestProgressRow,
)
from immortal_mmo.quest.repository import (
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
    StoredQuestOperation,
)


def _operation_from_row(row: QuestOperationRow) -> StoredQuestOperation:
    return StoredQuestOperation(
        operation_id=row.operation_id,
        account_id=row.account_id,
        life_id=row.life_id,
        command=QuestOperationCommand(row.command),
        quest_id=row.quest_id,
        provider_id=row.provider_id,
        request_fingerprint=row.request_fingerprint,
        state=QuestOperationState(row.state),
        changed=row.changed,
        response_status=row.response_status,
        response_content_type=row.response_content_type,
        response_body=bytes(row.response_body) if row.response_body is not None else None,
        response_contract_version=row.response_contract_version,
        created_at=row.created_at,
        finalized_at=row.finalized_at,
    )


def _progress_from_row(row: QuestProgressRow) -> QuestProgress:
    return QuestProgress(
        life_id=row.life_id,
        quest_id=row.quest_id,
        definition_version=row.definition_version,
        status=QuestProgressStatus(row.status),
        accepted_at=row.accepted_at,
        completed_at=row.completed_at,
        revision=row.revision,
    )


class PostgresQuestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_operation(self, operation_id: UUID) -> StoredQuestOperation | None:
        row = await self._session.scalar(
            select(QuestOperationRow).where(QuestOperationRow.operation_id == operation_id)
        )
        return _operation_from_row(row) if row is not None else None

    async def reserve_operation(self, operation: StoredQuestOperation) -> bool:
        inserted = await self._session.scalar(
            insert(QuestOperationRow)
            .values(
                operation_id=operation.operation_id,
                account_id=operation.account_id,
                life_id=operation.life_id,
                command=operation.command.value,
                quest_id=operation.quest_id,
                provider_id=operation.provider_id,
                request_fingerprint=operation.request_fingerprint,
                state=operation.state.value,
                changed=operation.changed,
                response_status=operation.response_status,
                response_content_type=operation.response_content_type,
                response_body=operation.response_body,
                response_contract_version=operation.response_contract_version,
                created_at=operation.created_at,
                finalized_at=operation.finalized_at,
            )
            .on_conflict_do_nothing(index_elements=[QuestOperationRow.operation_id])
            .returning(QuestOperationRow.operation_id)
        )
        return inserted is not None

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
        row = await self._session.scalar(
            update(QuestOperationRow)
            .where(
                QuestOperationRow.operation_id == operation_id,
                QuestOperationRow.state == QuestOperationState.PROCESSING.value,
            )
            .values(
                state=state.value,
                changed=changed,
                response_status=response_status,
                response_content_type=response_content_type,
                response_body=response_body,
                response_contract_version=response_contract_version,
                finalized_at=finalized_at,
            )
            .returning(QuestOperationRow)
        )
        if row is None:
            raise RuntimeError("Quest operation was not processing during finalization")
        return _operation_from_row(row)

    async def get_quest_revision(self, life_id: UUID, *, for_update: bool) -> int:
        if not for_update:
            revision = await self._session.scalar(
                select(LifeQuestStateRow.revision).where(
                    LifeQuestStateRow.life_id == life_id
                )
            )
            return revision if revision is not None else 0

        await self._session.execute(
            insert(LifeQuestStateRow)
            .values(life_id=life_id, revision=0)
            .on_conflict_do_nothing(index_elements=[LifeQuestStateRow.life_id])
        )
        revision = await self._session.scalar(
            select(LifeQuestStateRow.revision)
            .where(LifeQuestStateRow.life_id == life_id)
            .with_for_update(of=LifeQuestStateRow)
        )
        if revision is None:
            raise RuntimeError("Quest state disappeared after lazy insertion")
        return revision

    async def increment_quest_revision(self, life_id: UUID) -> int:
        revision = await self._session.scalar(
            update(LifeQuestStateRow)
            .where(LifeQuestStateRow.life_id == life_id)
            .values(
                revision=LifeQuestStateRow.revision + 1,
                updated_at=func.now(),
            )
            .returning(LifeQuestStateRow.revision)
        )
        if revision is None:
            raise RuntimeError("Quest state disappeared before revision increment")
        return revision

    async def get_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[str, QuestProgress]:
        if not quest_ids:
            return {}
        rows = (
            await self._session.scalars(
                select(QuestProgressRow).where(
                    QuestProgressRow.life_id == life_id,
                    QuestProgressRow.quest_id.in_(quest_ids),
                )
            )
        ).all()
        return {row.quest_id: _progress_from_row(row) for row in rows}

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        inserted = await self._session.scalar(
            insert(QuestProgressRow)
            .values(
                life_id=progress.life_id,
                quest_id=progress.quest_id,
                definition_version=progress.definition_version,
                status=progress.status.value,
                accepted_at=progress.accepted_at,
                completed_at=progress.completed_at,
                revision=progress.revision,
            )
            .on_conflict_do_nothing(
                index_elements=[QuestProgressRow.life_id, QuestProgressRow.quest_id]
            )
            .returning(QuestProgressRow.quest_id)
        )
        return inserted is not None

    async def complete_progress_if_active(
        self,
        life_id: UUID,
        quest_id: str,
        *,
        completed_at: datetime,
        revision: int,
    ) -> bool:
        updated = await self._session.scalar(
            update(QuestProgressRow)
            .where(
                QuestProgressRow.life_id == life_id,
                QuestProgressRow.quest_id == quest_id,
                QuestProgressRow.status == QuestProgressStatus.ACTIVE.value,
            )
            .values(
                status=QuestProgressStatus.COMPLETED.value,
                completed_at=completed_at,
                revision=revision,
                updated_at=func.now(),
            )
            .returning(QuestProgressRow.quest_id)
        )
        return updated is not None
