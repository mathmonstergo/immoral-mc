import hashlib
from collections.abc import Collection
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, cast, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.item.db_models import ItemInstanceRow, ItemResourceEntryRow, LifeItemStackRow
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


class PostgresItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending_instances(self, life_id: UUID) -> tuple[ItemInstance, ...]:
        rows = (
            await self._session.scalars(
                select(ItemInstanceRow)
                .where(
                    ItemInstanceRow.life_id == life_id,
                    ItemInstanceRow.status == ItemInstanceStatus.PENDING_DELIVERY.value,
                )
                .order_by(ItemInstanceRow.created_at, ItemInstanceRow.item_instance_id)
            )
        ).all()
        return tuple(_instance(row) for row in rows)

    async def count_pending_quest_reward_instances(
        self,
        quest_reward_grant_id: UUID,
    ) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(ItemInstanceRow)
            .where(
                ItemInstanceRow.quest_reward_grant_id == quest_reward_grant_id,
                ItemInstanceRow.status == ItemInstanceStatus.PENDING_DELIVERY.value,
            )
        )
        return int(count or 0)

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
        identities = tuple(item_instance_ids)
        if not identities or len(set(identities)) != len(identities):
            raise ValueError("Item instance identities must be non-empty and unique")
        if definition_version <= 0:
            raise ValueError("Item definition version must be positive")
        rows = [
            ItemInstanceRow(
                item_instance_id=item_instance_id,
                life_id=life_id,
                issuance_id=issuance_id,
                issuance_ordinal=ordinal,
                quest_reward_grant_id=quest_reward_grant_id,
                item_code=item_code,
                definition_version=definition_version,
                technique_id=technique_id,
                status=ItemInstanceStatus.PENDING_DELIVERY.value,
                created_at=created_at,
            )
            for ordinal, item_instance_id in enumerate(identities)
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return tuple(_instance(row) for row in rows)

    async def get_instance(
        self,
        item_instance_id: UUID,
        *,
        for_update: bool,
    ) -> ItemInstance | None:
        statement = select(ItemInstanceRow).where(
            ItemInstanceRow.item_instance_id == item_instance_id
        )
        if for_update:
            statement = statement.with_for_update(of=ItemInstanceRow)
        row = await self._session.scalar(statement)
        return None if row is None else _instance(row)

    async def get_instances(
        self,
        item_instance_ids: Collection[UUID],
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]:
        identities = tuple(sorted(set(item_instance_ids)))
        if not identities:
            return ()
        statement = (
            select(ItemInstanceRow)
            .where(ItemInstanceRow.item_instance_id.in_(identities))
            .order_by(ItemInstanceRow.item_instance_id)
        )
        if for_update:
            statement = statement.with_for_update(of=ItemInstanceRow)
        rows = (await self._session.scalars(statement)).all()
        return tuple(_instance(row) for row in rows)

    async def get_inventory_instances(
        self,
        life_id: UUID,
        item_codes: Collection[str] = (),
        *,
        for_update: bool,
    ) -> tuple[ItemInstance, ...]:
        statement = (
            select(ItemInstanceRow)
            .where(
                ItemInstanceRow.life_id == life_id,
                ItemInstanceRow.status == ItemInstanceStatus.OWNED.value,
                ItemInstanceRow.location == ItemLocation.INVENTORY.value,
            )
            .order_by(ItemInstanceRow.item_code, ItemInstanceRow.item_instance_id)
        )
        normalized = tuple(sorted(set(item_codes)))
        if normalized:
            statement = statement.where(ItemInstanceRow.item_code.in_(normalized))
        if for_update:
            statement = statement.with_for_update(of=ItemInstanceRow)
        rows = (await self._session.scalars(statement)).all()
        return tuple(_instance(row) for row in rows)

    async def set_instance_location(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        expected: ItemLocation,
        destination: ItemLocation,
    ) -> ItemInstance:
        if expected is destination:
            raise ValueError("Item location transition must change location")
        row = await self._session.scalar(
            update(ItemInstanceRow)
            .where(
                ItemInstanceRow.item_instance_id == item_instance_id,
                ItemInstanceRow.life_id == life_id,
                ItemInstanceRow.status == ItemInstanceStatus.OWNED.value,
                ItemInstanceRow.location == expected.value,
            )
            .values(location=destination.value)
            .returning(ItemInstanceRow)
        )
        if row is None:
            raise ItemOperationConflict("Item instance location changed")
        return _instance(row)

    async def confirm_delivery(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        delivered_at: datetime,
    ) -> ItemInstance:
        row = await self._session.scalar(
            select(ItemInstanceRow)
            .where(ItemInstanceRow.item_instance_id == item_instance_id)
            .with_for_update(of=ItemInstanceRow)
        )
        if row is None or row.life_id != life_id:
            raise KeyError("Item instance was not found for current life")
        if row.status in {
            ItemInstanceStatus.OWNED.value,
            ItemInstanceStatus.CONSUMED.value,
        }:
            return _instance(row)
        updated = await self._session.scalar(
            update(ItemInstanceRow)
            .where(
                ItemInstanceRow.item_instance_id == item_instance_id,
                ItemInstanceRow.life_id == life_id,
                ItemInstanceRow.status == ItemInstanceStatus.PENDING_DELIVERY.value,
            )
            .values(
                status=ItemInstanceStatus.OWNED.value,
                location=ItemLocation.INVENTORY.value,
                delivered_at=delivered_at,
            )
            .returning(ItemInstanceRow)
        )
        if updated is None:
            raise RuntimeError("Item delivery state changed during confirmation")
        return _instance(updated)

    async def consume_instance(
        self,
        *,
        item_instance_id: UUID,
        life_id: UUID,
        consumed_at: datetime,
    ) -> ItemInstance:
        row = await self._session.scalar(
            select(ItemInstanceRow)
            .where(ItemInstanceRow.item_instance_id == item_instance_id)
            .with_for_update(of=ItemInstanceRow)
        )
        if row is None or row.life_id != life_id:
            raise KeyError("Item instance was not found for current life")
        if row.status == ItemInstanceStatus.CONSUMED.value:
            return _instance(row)
        if row.status not in {
            ItemInstanceStatus.PENDING_DELIVERY.value,
            ItemInstanceStatus.OWNED.value,
        }:
            raise ItemOperationConflict("Item instance is not owned")
        updated = await self._session.scalar(
            update(ItemInstanceRow)
            .where(
                ItemInstanceRow.item_instance_id == item_instance_id,
                ItemInstanceRow.life_id == life_id,
                ItemInstanceRow.status == ItemInstanceStatus.OWNED.value,
            )
            .values(
                status=ItemInstanceStatus.CONSUMED.value,
                location=None,
                consumed_at=consumed_at,
            )
            .returning(ItemInstanceRow)
        )
        if updated is None:
            raise ItemOperationConflict("Item instance ownership changed")
        return _instance(updated)

    async def consume_inventory_instances(
        self,
        *,
        life_id: UUID,
        item_instance_ids: Collection[UUID],
        consumed_at: datetime,
    ) -> tuple[ItemInstance, ...]:
        identities = tuple(dict.fromkeys(item_instance_ids))
        if not identities:
            return ()
        locked = await self.get_instances(identities, for_update=True)
        by_id = {item.item_instance_id: item for item in locked}
        if len(by_id) != len(identities) or any(
            item_id not in by_id for item_id in identities
        ):
            raise KeyError("One or more item instances were not found")
        if any(
            item.life_id != life_id
            or item.status is not ItemInstanceStatus.OWNED
            or item.location is not ItemLocation.INVENTORY
            for item in locked
        ):
            raise ItemOperationConflict("One or more item instances are not in inventory")
        rows = (
            await self._session.scalars(
                update(ItemInstanceRow)
                .where(
                    ItemInstanceRow.item_instance_id.in_(identities),
                    ItemInstanceRow.life_id == life_id,
                    ItemInstanceRow.status == ItemInstanceStatus.OWNED.value,
                    ItemInstanceRow.location == ItemLocation.INVENTORY.value,
                )
                .values(
                    status=ItemInstanceStatus.CONSUMED.value,
                    location=None,
                    consumed_at=consumed_at,
                )
                .returning(ItemInstanceRow)
            )
        ).all()
        if len(rows) != len(identities):
            raise ItemOperationConflict("Item instance ownership changed")
        by_id = {row.item_instance_id: _instance(row) for row in rows}
        return tuple(by_id[item_id] for item_id in identities)

    async def get_stack(self, life_id: UUID, item_code: str, *, for_update: bool) -> ItemStack:
        row = await self._get_or_create_stack(life_id, item_code, for_update=for_update)
        return _stack(row)

    async def get_stacks(
        self,
        life_id: UUID,
        item_codes: Collection[str],
        *,
        for_update: bool,
    ) -> dict[str, ItemStack]:
        normalized = tuple(sorted(set(item_codes)))
        if not normalized:
            return {}
        if for_update:
            await self._session.execute(
                insert(LifeItemStackRow)
                .values(
                    [
                        {"life_id": life_id, "item_code": item_code}
                        for item_code in normalized
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[LifeItemStackRow.life_id, LifeItemStackRow.item_code]
                )
            )
        statement = (
            select(LifeItemStackRow)
            .where(
                LifeItemStackRow.life_id == life_id,
                LifeItemStackRow.item_code.in_(normalized),
            )
            .order_by(LifeItemStackRow.item_code)
        )
        if for_update:
            statement = statement.with_for_update(of=LifeItemStackRow)
        rows = (await self._session.scalars(statement)).all()
        return {row.item_code: _stack(row) for row in rows}

    async def adjust(
        self,
        *,
        life_id: UUID,
        item_code: str,
        delta_quantity: int,
        operation_id: UUID,
        occurred_at: datetime,
    ) -> ItemResourceEntry:
        if delta_quantity == 0:
            raise ValueError("Item adjustment delta must not be zero")
        await self._lock_operation_keys(((operation_id, item_code),))
        replay = await self._get_entry(operation_id, item_code)
        if replay is not None:
            if (
                replay.life_id != life_id
                or replay.session_id is not None
                or replay.entry_type != "administrative_adjustment"
                or replay.delta_quantity != delta_quantity
            ):
                raise ItemOperationConflict
            return replay
        row = await self._get_or_create_stack(life_id, item_code, for_update=True)
        balance_after = row.quantity + delta_quantity
        if balance_after < 0:
            raise InsufficientItemQuantity(item_code)
        updated = (
            await self._session.execute(
                update(LifeItemStackRow)
                .where(
                    LifeItemStackRow.life_id == life_id,
                    LifeItemStackRow.item_code == item_code,
                )
                .values(
                    quantity=balance_after,
                    revision=LifeItemStackRow.revision + 1,
                    updated_at=func.now(),
                )
                .returning(LifeItemStackRow.quantity)
            )
        ).one()
        entry = ItemResourceEntryRow(
            entry_id=uuid4(),
            life_id=life_id,
            item_code=item_code,
            operation_id=operation_id,
            session_id=None,
            entry_type="administrative_adjustment",
            delta_quantity=delta_quantity,
            balance_after=updated.quantity,
            created_at=occurred_at,
        )
        self._session.add(entry)
        await self._session.flush()
        return _entry(entry)

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
        requests = tuple(consumptions)
        if not requests:
            return ()
        if len({request.item_code for request in requests}) != len(requests):
            raise ValueError("Item consumption item codes must be unique")
        for request in requests:
            _validate_consumption_request(request)

        operation_keys = tuple(
            (request.operation_id, request.item_code) for request in requests
        )
        await self._lock_operation_keys(operation_keys)
        stored_rows = (
            await self._session.scalars(
                select(ItemResourceEntryRow).where(
                    tuple_(
                        ItemResourceEntryRow.operation_id,
                        ItemResourceEntryRow.item_code,
                    ).in_(operation_keys)
                )
            )
        ).all()
        replays = {
            (row.operation_id, row.item_code): _entry(row) for row in stored_rows
        }
        for request in requests:
            replay = replays.get((request.operation_id, request.item_code))
            if replay is not None:
                _validate_replay(life_id, request, replay)

        new_requests = tuple(
            request
            for request in requests
            if (request.operation_id, request.item_code) not in replays
        )
        if new_requests:
            stacks = await self.get_stacks(
                life_id,
                (request.item_code for request in new_requests),
                for_update=True,
            )
            for request in new_requests:
                stack = stacks[request.item_code]
                if stack.quantity < request.quantity:
                    raise InsufficientItemQuantity(request.item_code)
            for request in new_requests:
                stack = stacks[request.item_code]
                balance_after = stack.quantity - request.quantity
                await self._session.execute(
                    update(LifeItemStackRow)
                    .where(
                        LifeItemStackRow.life_id == life_id,
                        LifeItemStackRow.item_code == request.item_code,
                    )
                    .values(
                        quantity=balance_after,
                        revision=LifeItemStackRow.revision + 1,
                        updated_at=func.now(),
                    )
                )
                entry = ItemResourceEntryRow(
                    entry_id=uuid4(),
                    life_id=life_id,
                    item_code=request.item_code,
                    operation_id=request.operation_id,
                    session_id=request.session_id,
                    entry_type=request.entry_type.value,
                    delta_quantity=-request.quantity,
                    balance_after=balance_after,
                    created_at=request.occurred_at,
                )
                self._session.add(entry)
                replays[(request.operation_id, request.item_code)] = _entry(entry)
                stacks[request.item_code] = ItemStack(
                    life_id=life_id,
                    item_code=request.item_code,
                    quantity=balance_after,
                    revision=stack.revision + 1,
                )
            await self._session.flush()

        return tuple(
            replays[(request.operation_id, request.item_code)] for request in requests
        )

    async def _lock_operation_keys(
        self,
        operation_keys: Collection[tuple[UUID, str]],
    ) -> None:
        # Sort physical keys so overlapping batches cannot deadlock while acquiring locks.
        lock_keys = sorted(
            {
                _item_operation_lock_key(operation_id, item_code)
                for operation_id, item_code in operation_keys
            }
        )
        for lock_key in lock_keys:
            await self._session.execute(
                select(func.pg_advisory_xact_lock(cast(lock_key, BigInteger)))
            )

    async def _get_or_create_stack(
        self, life_id: UUID, item_code: str, *, for_update: bool
    ) -> LifeItemStackRow:
        await self._session.execute(
            insert(LifeItemStackRow)
            .values(life_id=life_id, item_code=item_code)
            .on_conflict_do_nothing(
                index_elements=[LifeItemStackRow.life_id, LifeItemStackRow.item_code]
            )
        )
        statement = select(LifeItemStackRow).where(
            LifeItemStackRow.life_id == life_id,
            LifeItemStackRow.item_code == item_code,
        )
        if for_update:
            statement = statement.with_for_update(of=LifeItemStackRow)
        row = await self._session.scalar(statement)
        if row is None:
            raise RuntimeError("Item stack disappeared after initialization")
        return row

    async def _get_entry(self, operation_id: UUID, item_code: str) -> ItemResourceEntry | None:
        row = await self._session.scalar(
            select(ItemResourceEntryRow).where(
                ItemResourceEntryRow.operation_id == operation_id,
                ItemResourceEntryRow.item_code == item_code,
            )
        )
        return None if row is None else _entry(row)


def _validate_consumption_request(request: ItemConsumptionRequest) -> None:
    if request.quantity <= 0:
        raise ValueError("Consumed item quantity must be positive")
    if (
        request.entry_type is ItemConsumptionType.BREAKTHROUGH
        and request.session_id is None
    ):
        raise ValueError("Breakthrough consumption requires a session ID")


def _item_operation_lock_key(operation_id: UUID, item_code: str) -> int:
    digest = hashlib.sha256(
        b"immortal-mmo:item-operation:v1\0"
        + operation_id.bytes
        + item_code.encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _validate_replay(
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


def _stack(row: LifeItemStackRow) -> ItemStack:
    return ItemStack(
        life_id=row.life_id,
        item_code=row.item_code,
        quantity=row.quantity,
        revision=row.revision,
    )


def _entry(row: ItemResourceEntryRow) -> ItemResourceEntry:
    return ItemResourceEntry(
        entry_id=row.entry_id,
        life_id=row.life_id,
        item_code=row.item_code,
        operation_id=row.operation_id,
        session_id=row.session_id,
        entry_type=row.entry_type,
        delta_quantity=row.delta_quantity,
        balance_after=row.balance_after,
        created_at=row.created_at,
    )


def _instance(row: ItemInstanceRow) -> ItemInstance:
    return ItemInstance(
        item_instance_id=row.item_instance_id,
        life_id=row.life_id,
        item_code=row.item_code,
        definition_version=row.definition_version,
        technique_id=row.technique_id,
        issuance_id=row.issuance_id,
        issuance_ordinal=row.issuance_ordinal,
        quest_reward_grant_id=row.quest_reward_grant_id,
        status=ItemInstanceStatus(row.status),
        created_at=row.created_at,
        delivered_at=row.delivered_at,
        consumed_at=row.consumed_at,
        location=None if row.location is None else ItemLocation(row.location),
    )
