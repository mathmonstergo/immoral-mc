from collections.abc import Collection
from typing import Protocol
from uuid import UUID

from immortal_mmo.storage.models import (
    StorageContainer,
    StorageOperation,
    StorageSlot,
)


class StorageRepository(Protocol):
    async def lock_operation(self, operation_id: UUID) -> None: ...

    async def get_container(
        self,
        life_id: UUID,
        area_id: str,
        *,
        for_update: bool,
    ) -> StorageContainer | None: ...

    async def create_container(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page_count: int,
        item_slots_per_page: int,
    ) -> StorageContainer: ...

    async def get_page_slots(
        self,
        life_id: UUID,
        area_id: str,
        page: int,
    ) -> tuple[StorageSlot, ...]: ...

    async def get_slots(
        self,
        life_id: UUID,
        area_id: str,
        positions: Collection[tuple[int, int]],
        *,
        for_update: bool,
    ) -> dict[tuple[int, int], StorageSlot]: ...

    async def find_item_slot(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> StorageSlot | None: ...

    async def put_slot(self, slot: StorageSlot) -> None: ...

    async def delete_slot(
        self,
        *,
        life_id: UUID,
        area_id: str,
        page: int,
        slot: int,
        item_instance_id: UUID,
    ) -> None: ...

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
    ) -> None: ...

    async def increment_revision(
        self,
        *,
        life_id: UUID,
        area_id: str,
        expected_revision: int,
    ) -> int: ...

    async def get_operation(self, operation_id: UUID) -> StorageOperation | None: ...

    async def insert_operation(self, operation: StorageOperation) -> None: ...
