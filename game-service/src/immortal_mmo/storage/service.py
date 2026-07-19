import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from immortal_mmo.core.uow import UnitOfWork, UnitOfWorkFactory
from immortal_mmo.item.models import (
    ItemInstance,
    ItemInstanceStatus,
    ItemLocation,
    ItemOperationConflict,
)
from immortal_mmo.item.schemas import ItemInstanceProjection
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError
from immortal_mmo.storage.catalog import (
    StorageCatalog,
    StorageDefinition,
    load_storage_catalog,
)
from immortal_mmo.storage.errors import (
    StorageAreaNotFoundError,
    StorageMoveRuleError,
    StorageOperationConflictError,
    StoragePageNotFoundError,
    StorageRevisionConflictError,
)
from immortal_mmo.storage.models import StorageMoveKind, StorageOperation, StorageSlot
from immortal_mmo.storage.schemas import (
    StorageMoveRequest,
    StorageMoveResponse,
    StorageSlotProjection,
    StorageSnapshotResponse,
)


class StorageService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        catalog: StorageCatalog | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog or load_storage_catalog(
            Path(__file__).resolve().parent / "catalog.json"
        )
        self._clock = clock or (lambda: datetime.now(UTC))

    async def snapshot(
        self,
        *,
        account_id: UUID,
        area_id: str,
        page: int,
    ) -> StorageSnapshotResponse:
        definition = self._definition(area_id)
        self._validate_page(definition, page)
        async with self._uow_factory(isolation="repeatable_read") as uow:
            life_id = await self._current_life_id(uow, account_id, for_update=False)
            container = await uow.storage.get_container(
                life_id,
                area_id,
                for_update=False,
            )
            if container is None:
                await uow.rollback()
                return StorageSnapshotResponse(
                    life_id=life_id,
                    area_id=area_id,
                    catalog_revision=self._catalog.revision,
                    permission=definition.permission,
                    page=page,
                    page_count=definition.page_count,
                    item_slots_per_page=definition.item_slots_per_page,
                    revision=0,
                    slots=[],
                )
            snapshot = await self._snapshot(
                uow,
                life_id=life_id,
                definition=definition,
                page=page,
                revision=container.revision,
            )
            await uow.rollback()
            return snapshot

    async def move(
        self,
        *,
        account_id: UUID,
        area_id: str,
        operation_id: UUID,
        request: StorageMoveRequest,
    ) -> StorageMoveResponse:
        definition = self._definition(area_id)
        self._validate_request_positions(definition, request)
        fingerprint = _fingerprint(account_id, area_id, request)
        async with self._uow_factory() as uow:
            await uow.storage.lock_operation(operation_id)
            life_id = await self._current_life_id(uow, account_id, for_update=True)
            replay = await uow.storage.get_operation(operation_id)
            if replay is not None:
                if (
                    replay.life_id != life_id
                    or replay.area_id != area_id
                    or replay.request_fingerprint != fingerprint
                ):
                    raise StorageOperationConflictError()
                await uow.rollback()
                return StorageMoveResponse.model_validate_json(replay.response_body)

            container = await uow.storage.create_container(
                life_id=life_id,
                area_id=area_id,
                page_count=definition.page_count,
                item_slots_per_page=definition.item_slots_per_page,
            )
            if container.revision != request.expected_revision:
                raise StorageRevisionConflictError()

            item = await uow.items.get_instance(request.item_instance_id, for_update=True)
            if item is None or item.life_id != life_id:
                raise StorageMoveRuleError("Item does not belong to the current life")
            positions = tuple(
                position
                for position in (
                    _position(request.source_page, request.source_slot),
                    _position(request.destination_page, request.destination_slot),
                )
                if position is not None
            )
            slots = await uow.storage.get_slots(
                life_id,
                area_id,
                positions,
                for_update=True,
            )
            move_kind = StorageMoveKind(request.move_kind)
            try:
                await self._apply_move(
                    uow,
                    life_id=life_id,
                    area_id=area_id,
                    definition=definition,
                    move_kind=move_kind,
                    request=request,
                    item=item,
                    slots=slots,
                )
            except ItemOperationConflict as error:
                raise StorageMoveRuleError() from error
            revision = await uow.storage.increment_revision(
                life_id=life_id,
                area_id=area_id,
                expected_revision=request.expected_revision,
            )
            response = StorageMoveResponse(
                operation_id=operation_id,
                move_kind=move_kind.value,
                item_instance_id=item.item_instance_id,
                snapshot=await self._snapshot(
                    uow,
                    life_id=life_id,
                    definition=definition,
                    page=request.view_page,
                    revision=revision,
                ),
            )
            await uow.storage.insert_operation(
                StorageOperation(
                    operation_id=operation_id,
                    life_id=life_id,
                    area_id=area_id,
                    move_kind=move_kind,
                    item_instance_id=item.item_instance_id,
                    expected_revision=request.expected_revision,
                    resulting_revision=revision,
                    source_page=request.source_page,
                    source_slot=request.source_slot,
                    destination_page=request.destination_page,
                    destination_slot=request.destination_slot,
                    view_page=request.view_page,
                    request_fingerprint=fingerprint,
                    response_body=response.model_dump_json().encode(),
                    created_at=self._clock(),
                )
            )
            await uow.commit()
            return response

    async def _apply_move(
        self,
        uow: UnitOfWork,
        *,
        life_id: UUID,
        area_id: str,
        definition: StorageDefinition,
        move_kind: StorageMoveKind,
        request: StorageMoveRequest,
        item: ItemInstance,
        slots: dict[tuple[int, int], StorageSlot],
    ) -> None:
        source = _position(request.source_page, request.source_slot)
        destination = _position(request.destination_page, request.destination_slot)
        now = self._clock()
        if move_kind is StorageMoveKind.DEPOSIT:
            if item.location is not ItemLocation.INVENTORY or destination in slots:
                raise StorageMoveRuleError()
            existing_slot = await uow.storage.find_item_slot(
                item.item_instance_id,
                for_update=True,
            )
            if existing_slot is not None:
                raise StorageMoveRuleError()
            await uow.items.set_instance_location(
                item_instance_id=item.item_instance_id,
                life_id=life_id,
                expected=ItemLocation.INVENTORY,
                destination=ItemLocation.STORAGE,
            )
            await uow.storage.put_slot(
                StorageSlot(
                    life_id=life_id,
                    area_id=area_id,
                    page=destination[0],
                    slot=destination[1],
                    item_instance_id=item.item_instance_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            return
        source_record = slots.get(source)
        if (
            item.location is not ItemLocation.STORAGE
            or source_record is None
            or source_record.item_instance_id != item.item_instance_id
        ):
            raise StorageMoveRuleError()
        if move_kind is StorageMoveKind.WITHDRAW:
            await uow.storage.delete_slot(
                life_id=life_id,
                area_id=area_id,
                page=source[0],
                slot=source[1],
                item_instance_id=item.item_instance_id,
            )
            await uow.items.set_instance_location(
                item_instance_id=item.item_instance_id,
                life_id=life_id,
                expected=ItemLocation.STORAGE,
                destination=ItemLocation.INVENTORY,
            )
            return
        destination_record = slots.get(destination)
        if destination_record is not None:
            await uow.storage.delete_slot(
                life_id=life_id,
                area_id=area_id,
                page=source[0],
                slot=source[1],
                item_instance_id=source_record.item_instance_id,
            )
            await uow.storage.delete_slot(
                life_id=life_id,
                area_id=area_id,
                page=destination[0],
                slot=destination[1],
                item_instance_id=destination_record.item_instance_id,
            )
            await uow.storage.put_slot(
                StorageSlot(
                    life_id=life_id,
                    area_id=area_id,
                    page=source[0],
                    slot=source[1],
                    item_instance_id=destination_record.item_instance_id,
                    created_at=destination_record.created_at,
                    updated_at=now,
                )
            )
            await uow.storage.put_slot(
                StorageSlot(
                    life_id=life_id,
                    area_id=area_id,
                    page=destination[0],
                    slot=destination[1],
                    item_instance_id=source_record.item_instance_id,
                    created_at=source_record.created_at,
                    updated_at=now,
                )
            )
            return
        await uow.storage.move_slot(
            life_id=life_id,
            area_id=area_id,
            source_page=source[0],
            source_slot=source[1],
            destination_page=destination[0],
            destination_slot=destination[1],
            item_instance_id=item.item_instance_id,
        )

    async def _snapshot(
        self,
        uow: UnitOfWork,
        *,
        life_id: UUID,
        definition: StorageDefinition,
        page: int,
        revision: int,
    ) -> StorageSnapshotResponse:
        slots = await uow.storage.get_page_slots(life_id, definition.area_id, page)
        items = await uow.items.get_instances(
            (slot.item_instance_id for slot in slots),
            for_update=False,
        )
        by_id = {item.item_instance_id: item for item in items}
        if len(by_id) != len(slots):
            raise RuntimeError("Storage slot references a missing item instance")
        if any(
            item.status is not ItemInstanceStatus.OWNED
            or item.location is not ItemLocation.STORAGE
            for item in items
        ):
            raise RuntimeError("Storage slot references an item outside storage")
        return StorageSnapshotResponse(
            life_id=life_id,
            area_id=definition.area_id,
            catalog_revision=self._catalog.revision,
            permission=definition.permission,
            page=page,
            page_count=definition.page_count,
            item_slots_per_page=definition.item_slots_per_page,
            revision=revision,
            slots=[
                StorageSlotProjection(
                    slot=slot.slot,
                    item=_item_projection(by_id[slot.item_instance_id]),
                )
                for slot in slots
            ],
        )

    async def _current_life_id(
        self,
        uow: UnitOfWork,
        account_id: UUID,
        *,
        for_update: bool,
    ) -> UUID:
        account = await uow.players.lock_account(account_id)
        if account is None:
            raise PlayerAccountNotFoundError()
        life = await uow.players.get_current_life(account_id, for_update=for_update)
        if life is None:
            raise PlayerLifecycleError()
        return life.life_id

    def _definition(self, area_id: str) -> StorageDefinition:
        try:
            return self._catalog.storage(area_id)
        except KeyError as error:
            raise StorageAreaNotFoundError() from error

    @staticmethod
    def _validate_page(definition: StorageDefinition, page: int) -> None:
        if not 1 <= page <= definition.page_count:
            raise StoragePageNotFoundError()

    def _validate_request_positions(
        self,
        definition: StorageDefinition,
        request: StorageMoveRequest,
    ) -> None:
        self._validate_page(definition, request.view_page)
        positions = (
            _position(request.source_page, request.source_slot),
            _position(request.destination_page, request.destination_slot),
        )
        for position in positions:
            if position is None:
                continue
            page, slot = position
            self._validate_page(definition, page)
            if not 0 <= slot < definition.item_slots_per_page:
                raise StorageMoveRuleError("Storage slot is outside the item range")


def _position(page: int | None, slot: int | None) -> tuple[int, int] | None:
    if page is None or slot is None:
        return None
    return page, slot


def _fingerprint(
    account_id: UUID,
    area_id: str,
    request: StorageMoveRequest,
) -> str:
    document = {
        "account_id": str(account_id),
        "area_id": area_id,
        **request.model_dump(mode="json"),
    }
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _item_projection(item: ItemInstance) -> ItemInstanceProjection:
    return ItemInstanceProjection(
        item_instance_id=item.item_instance_id,
        item_code=item.item_code,
        definition_version=item.definition_version,
        technique_id=item.technique_id,
        status=item.status.value,
        location=None if item.location is None else item.location.value,
    )
