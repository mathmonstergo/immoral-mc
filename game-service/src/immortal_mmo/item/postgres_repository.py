import hashlib
from collections.abc import Collection
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, cast, func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.item.db_models import ItemResourceEntryRow, LifeItemStackRow
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemConsumptionRequest,
    ItemConsumptionType,
    ItemOperationConflict,
    ItemResourceEntry,
    ItemStack,
)


class PostgresItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    if (
        request.entry_type is ItemConsumptionType.QUEST_DELIVERY
        and request.session_id is not None
    ):
        raise ValueError("Quest delivery must not have a cultivation session ID")


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
