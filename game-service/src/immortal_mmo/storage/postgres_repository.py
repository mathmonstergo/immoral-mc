import hashlib
from collections.abc import Collection
from uuid import UUID

from sqlalchemy import BigInteger, cast, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.storage.db_models import (
    RegionalStorageContainerRow,
    RegionalStorageOperationRow,
    RegionalStorageSlotRow,
)
from immortal_mmo.storage.models import (
    StorageContainer,
    StorageMoveKind,
    StorageOperation,
    StorageSlot,
)


class PostgresStorageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_operation(self, operation_id: UUID) -> None:
        await self._session.execute(
            select(func.pg_advisory_xact_lock(cast(_operation_lock_key(operation_id), BigInteger)))
        )

    async def get_container(
        self,
        life_id: UUID,
        area_id: str,
        *,
        for_update: bool,
    ) -> StorageContainer | None:
        statement = select(RegionalStorageContainerRow).where(
            RegionalStorageContainerRow.life_id == life_id,
            RegionalStorageContainerRow.area_id == area_id,
        )
        if for_update:
            statement = statement.with_for_update(of=RegionalStorageContainerRow)
        row = await self._session.scalar(statement)
        return None if row is None else _container(row)

    async def create_container(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page_count: int,
        item_slots_per_page: int,
    ) -> StorageContainer:
        await self._session.execute(
            insert(RegionalStorageContainerRow)
            .values(
                life_id=life_id,
                area_id=area_id,
                page_count=page_count,
                item_slots_per_page=item_slots_per_page,
                revision=0,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    RegionalStorageContainerRow.life_id,
                    RegionalStorageContainerRow.area_id,
                ]
            )
        )
        container = await self.get_container(life_id, area_id, for_update=True)
        if container is None:
            raise RuntimeError("Storage container disappeared after initialization")
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
        rows = (
            await self._session.scalars(
                select(RegionalStorageSlotRow)
                .where(
                    RegionalStorageSlotRow.life_id == life_id,
                    RegionalStorageSlotRow.area_id == area_id,
                    RegionalStorageSlotRow.page == page,
                )
                .order_by(RegionalStorageSlotRow.slot)
            )
        ).all()
        return tuple(_slot(row) for row in rows)

    async def get_slots(
        self,
        life_id: UUID,
        area_id: str,
        positions: Collection[tuple[int, int]],
        *,
        for_update: bool,
    ) -> dict[tuple[int, int], StorageSlot]:
        normalized = tuple(sorted(set(positions)))
        if not normalized:
            return {}
        conditions = [
            (RegionalStorageSlotRow.page == page)
            & (RegionalStorageSlotRow.slot == slot)
            for page, slot in normalized
        ]
        statement = (
            select(RegionalStorageSlotRow)
            .where(
                RegionalStorageSlotRow.life_id == life_id,
                RegionalStorageSlotRow.area_id == area_id,
                or_(*conditions),
            )
            .order_by(RegionalStorageSlotRow.page, RegionalStorageSlotRow.slot)
        )
        if for_update:
            statement = statement.with_for_update(of=RegionalStorageSlotRow)
        rows = (await self._session.scalars(statement)).all()
        return {(row.page, row.slot): _slot(row) for row in rows}

    async def find_item_slot(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> StorageSlot | None:
        statement = select(RegionalStorageSlotRow).where(
            RegionalStorageSlotRow.item_instance_id == item_instance_id
        )
        if for_update:
            statement = statement.with_for_update(of=RegionalStorageSlotRow)
        row = await self._session.scalar(statement)
        return None if row is None else _slot(row)

    async def put_slot(self, slot: StorageSlot) -> None:
        self._session.add(
            RegionalStorageSlotRow(
                life_id=slot.life_id,
                area_id=slot.area_id,
                page=slot.page,
                slot=slot.slot,
                item_instance_id=slot.item_instance_id,
                created_at=slot.created_at,
                updated_at=slot.updated_at,
            )
        )
        await self._session.flush()

    async def delete_slot(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page: int,
        slot: int,
        item_instance_id: UUID,
    ) -> None:
        result = await self._session.execute(
            delete(RegionalStorageSlotRow).where(
                RegionalStorageSlotRow.life_id == life_id,
                RegionalStorageSlotRow.area_id == area_id,
                RegionalStorageSlotRow.page == page,
                RegionalStorageSlotRow.slot == slot,
                RegionalStorageSlotRow.item_instance_id == item_instance_id,
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("Storage slot changed before removal")

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
        result = await self._session.execute(
            update(RegionalStorageSlotRow)
            .where(
                RegionalStorageSlotRow.life_id == life_id,
                RegionalStorageSlotRow.area_id == area_id,
                RegionalStorageSlotRow.page == source_page,
                RegionalStorageSlotRow.slot == source_slot,
                RegionalStorageSlotRow.item_instance_id == item_instance_id,
            )
            .values(
                page=destination_page,
                slot=destination_slot,
                updated_at=func.now(),
            )
        )
        if result.rowcount != 1:
            raise RuntimeError("Storage source slot changed before move")

    async def increment_revision(
        self,
        *,
        life_id: UUID,
        area_id: str,
        expected_revision: int,
    ) -> int:
        revision = await self._session.scalar(
            update(RegionalStorageContainerRow)
            .where(
                RegionalStorageContainerRow.life_id == life_id,
                RegionalStorageContainerRow.area_id == area_id,
                RegionalStorageContainerRow.revision == expected_revision,
            )
            .values(
                revision=RegionalStorageContainerRow.revision + 1,
                updated_at=func.now(),
            )
            .returning(RegionalStorageContainerRow.revision)
        )
        if revision is None:
            raise RuntimeError("Storage revision changed before mutation")
        return revision

    async def get_operation(self, operation_id: UUID) -> StorageOperation | None:
        row = await self._session.get(RegionalStorageOperationRow, operation_id)
        return None if row is None else _operation(row)

    async def insert_operation(self, operation: StorageOperation) -> None:
        self._session.add(
            RegionalStorageOperationRow(
                operation_id=operation.operation_id,
                life_id=operation.life_id,
                area_id=operation.area_id,
                move_kind=operation.move_kind.value,
                item_instance_id=operation.item_instance_id,
                expected_revision=operation.expected_revision,
                resulting_revision=operation.resulting_revision,
                source_page=operation.source_page,
                source_slot=operation.source_slot,
                destination_page=operation.destination_page,
                destination_slot=operation.destination_slot,
                view_page=operation.view_page,
                request_fingerprint=operation.request_fingerprint,
                response_body=operation.response_body,
                created_at=operation.created_at,
            )
        )
        await self._session.flush()


def _container(row: RegionalStorageContainerRow) -> StorageContainer:
    return StorageContainer(
        life_id=row.life_id,
        area_id=row.area_id,
        page_count=row.page_count,
        item_slots_per_page=row.item_slots_per_page,
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _slot(row: RegionalStorageSlotRow) -> StorageSlot:
    return StorageSlot(
        life_id=row.life_id,
        area_id=row.area_id,
        page=row.page,
        slot=row.slot,
        item_instance_id=row.item_instance_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _operation(row: RegionalStorageOperationRow) -> StorageOperation:
    return StorageOperation(
        operation_id=row.operation_id,
        life_id=row.life_id,
        area_id=row.area_id,
        move_kind=StorageMoveKind(row.move_kind),
        item_instance_id=row.item_instance_id,
        expected_revision=row.expected_revision,
        resulting_revision=row.resulting_revision,
        source_page=row.source_page,
        source_slot=row.source_slot,
        destination_page=row.destination_page,
        destination_slot=row.destination_slot,
        view_page=row.view_page,
        request_fingerprint=row.request_fingerprint,
        response_body=bytes(row.response_body),
        created_at=row.created_at,
    )


def _operation_lock_key(operation_id: UUID) -> int:
    digest = hashlib.sha256(
        b"immortal-mmo:regional-storage-operation:v1\0" + operation_id.bytes
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)
