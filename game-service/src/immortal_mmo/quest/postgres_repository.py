from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.quest.db_models import (
    LifeQuestStateRow,
    QuestObjectiveProgressRow,
    QuestOperationRow,
    QuestProgressRow,
    QuestRewardGrantRow,
)
from immortal_mmo.quest.repository import (
    QuestObjectiveProgress,
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
    QuestRewardGrant,
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


def _objective_progress_from_row(row: QuestObjectiveProgressRow) -> QuestObjectiveProgress:
    return QuestObjectiveProgress(
        life_id=row.life_id,
        quest_id=row.quest_id,
        objective_id=row.objective_id,
        definition_version=row.definition_version,
        objective_type=row.objective_type,
        target_id=row.target_id,
        required_value=row.required_value,
        current_value=row.current_value,
        updated_at=row.updated_at,
    )


def _reward_grant_from_row(row: QuestRewardGrantRow) -> QuestRewardGrant:
    from immortal_mmo.quest.models import QuestRewardType

    return QuestRewardGrant(
        grant_id=row.grant_id,
        life_id=row.life_id,
        operation_id=row.operation_id,
        quest_id=row.quest_id,
        reward_id=row.reward_id,
        reward_type=QuestRewardType(row.reward_type),
        item_code=row.item_code,
        configured_amount=row.configured_amount,
        applied_amount=row.applied_amount,
        pending_amount=row.pending_amount,
        status=row.status,
        created_at=row.created_at,
    )


class PostgresQuestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_reward_grant(self, grant: QuestRewardGrant) -> None:
        self._session.add(
            QuestRewardGrantRow(
                grant_id=grant.grant_id,
                life_id=grant.life_id,
                operation_id=grant.operation_id,
                quest_id=grant.quest_id,
                reward_id=grant.reward_id,
                reward_type=grant.reward_type.value,
                item_code=grant.item_code,
                configured_amount=grant.configured_amount,
                applied_amount=grant.applied_amount,
                pending_amount=grant.pending_amount,
                status=grant.status,
                created_at=grant.created_at,
            )
        )
        await self._session.flush()

    async def get_reward_grants(
        self,
        operation_id: UUID,
    ) -> tuple[QuestRewardGrant, ...]:
        rows = (
            await self._session.scalars(
                select(QuestRewardGrantRow)
                .where(QuestRewardGrantRow.operation_id == operation_id)
                .order_by(QuestRewardGrantRow.reward_id)
            )
        ).all()
        return tuple(_reward_grant_from_row(row) for row in rows)

    async def get_reward_grant(self, grant_id: UUID) -> QuestRewardGrant | None:
        row = await self._session.get(QuestRewardGrantRow, grant_id)
        return None if row is None else _reward_grant_from_row(row)

    async def update_reward_grant_progress(
        self,
        *,
        grant_id: UUID,
        pending_amount: int,
    ) -> QuestRewardGrant:
        row = await self._session.scalar(
            update(QuestRewardGrantRow)
            .where(
                QuestRewardGrantRow.grant_id == grant_id,
                QuestRewardGrantRow.pending_amount >= pending_amount,
            )
            .values(
                applied_amount=QuestRewardGrantRow.configured_amount - pending_amount,
                pending_amount=pending_amount,
                status="applied" if pending_amount == 0 else "pending",
            )
            .returning(QuestRewardGrantRow)
        )
        if row is None:
            raise KeyError("Quest reward grant was not found or is not mutable")
        return _reward_grant_from_row(row)

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

    async def get_objective_progresses(
        self,
        life_id: UUID,
        quest_ids: Collection[str],
    ) -> dict[tuple[str, str], QuestObjectiveProgress]:
        if not quest_ids:
            return {}
        rows = (
            await self._session.scalars(
                select(QuestObjectiveProgressRow).where(
                    QuestObjectiveProgressRow.life_id == life_id,
                    QuestObjectiveProgressRow.quest_id.in_(quest_ids),
                )
            )
        ).all()
        return {
            (row.quest_id, row.objective_id): _objective_progress_from_row(row)
            for row in rows
        }

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

    async def insert_objective_progresses(
        self,
        progresses: Collection[QuestObjectiveProgress],
    ) -> None:
        rows = [
            QuestObjectiveProgressRow(
                life_id=progress.life_id,
                quest_id=progress.quest_id,
                objective_id=progress.objective_id,
                definition_version=progress.definition_version,
                objective_type=progress.objective_type,
                target_id=progress.target_id,
                required_value=progress.required_value,
                current_value=progress.current_value,
                updated_at=progress.updated_at,
            )
            for progress in progresses
        ]
        if not rows:
            return
        self._session.add_all(rows)
        await self._session.flush()

    async def increment_objective_progress(
        self,
        *,
        life_id: UUID,
        quest_id: str,
        objective_id: str,
        required_value: int,
        updated_at: datetime,
    ) -> int | None:
        return await self._session.scalar(
            update(QuestObjectiveProgressRow)
            .where(
                QuestObjectiveProgressRow.life_id == life_id,
                QuestObjectiveProgressRow.quest_id == quest_id,
                QuestObjectiveProgressRow.objective_id == objective_id,
                QuestObjectiveProgressRow.required_value == required_value,
                QuestObjectiveProgressRow.current_value < required_value,
            )
            .values(
                current_value=func.least(
                    QuestObjectiveProgressRow.current_value + 1,
                    required_value,
                ),
                updated_at=updated_at,
            )
            .returning(QuestObjectiveProgressRow.current_value)
        )

    async def increment_objective_progresses(
        self,
        *,
        life_id: UUID,
        objectives: Collection[tuple[str, str]],
        updated_at: datetime,
    ) -> dict[tuple[str, str], int]:
        keys = tuple(sorted(set(objectives)))
        if not keys:
            return {}
        rows = (
            await self._session.execute(
                update(QuestObjectiveProgressRow)
                .where(
                    QuestObjectiveProgressRow.life_id == life_id,
                    tuple_(
                        QuestObjectiveProgressRow.quest_id,
                        QuestObjectiveProgressRow.objective_id,
                    ).in_(keys),
                    QuestObjectiveProgressRow.current_value
                    < QuestObjectiveProgressRow.required_value,
                )
                .values(
                    current_value=func.least(
                        QuestObjectiveProgressRow.current_value + 1,
                        QuestObjectiveProgressRow.required_value,
                    ),
                    updated_at=updated_at,
                )
                .returning(
                    QuestObjectiveProgressRow.quest_id,
                    QuestObjectiveProgressRow.objective_id,
                    QuestObjectiveProgressRow.current_value,
                )
            )
        ).all()
        return {
            (quest_id, objective_id): current_value
            for quest_id, objective_id, current_value in rows
        }

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
