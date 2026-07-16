from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.item.db_models import ItemResourceEntryRow, LifeItemStackRow
from immortal_mmo.item.models import (
    InsufficientItemQuantity,
    ItemResourceEntry,
    ItemStack,
)


class PostgresItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_stack(self, life_id: UUID, item_code: str, *, for_update: bool) -> ItemStack:
        row = await self._get_or_create_stack(life_id, item_code, for_update=for_update)
        return _stack(row)

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
        replay = await self._get_entry(operation_id, item_code)
        if replay is not None:
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
        session_id: UUID | None,
        occurred_at: datetime,
    ) -> ItemResourceEntry:
        if quantity <= 0:
            raise ValueError("Consumed item quantity must be positive")
        replay = await self._get_entry(operation_id, item_code)
        if replay is not None:
            return replay
        row = await self._get_or_create_stack(life_id, item_code, for_update=True)
        if row.quantity < quantity:
            raise InsufficientItemQuantity(item_code)
        balance_after = row.quantity - quantity
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
        )
        entry = ItemResourceEntryRow(
            entry_id=uuid4(),
            life_id=life_id,
            item_code=item_code,
            operation_id=operation_id,
            session_id=session_id,
            entry_type="breakthrough_consumption",
            delta_quantity=-quantity,
            balance_after=balance_after,
            created_at=occurred_at,
        )
        self._session.add(entry)
        await self._session.flush()
        return _entry(entry)

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
