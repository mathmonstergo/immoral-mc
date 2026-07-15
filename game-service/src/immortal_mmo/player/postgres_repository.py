from uuid import UUID, uuid4

from sqlalchemy import case, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from immortal_mmo.player.db_models import (
    AccountMinecraftNameRow,
    AccountRow,
    LifeRow,
    LifeSpiritRootRow,
)
from immortal_mmo.player.mappers import account_from_row, life_from_row, spirit_root_from_row
from immortal_mmo.player.models import Account, CurrentLifeQuestFacts, Life, SpiritRoot


class PostgresPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_account(self, minecraft_uuid: UUID, last_known_name: str) -> Account:
        account_insert = insert(AccountRow).values(
            account_id=uuid4(),
            minecraft_uuid=minecraft_uuid,
            last_known_name=last_known_name,
        )
        account_row = (
            await self._session.execute(
                account_insert.on_conflict_do_update(
                    index_elements=[AccountRow.minecraft_uuid],
                    set_={
                        "last_known_name": account_insert.excluded.last_known_name,
                        "revision": case(
                            (
                                AccountRow.last_known_name
                                != account_insert.excluded.last_known_name,
                                AccountRow.revision + 1,
                            ),
                            else_=AccountRow.revision,
                        ),
                        "updated_at": func.greatest(
                            AccountRow.updated_at,
                            func.clock_timestamp(),
                        ),
                        "last_seen_at": func.greatest(
                            AccountRow.last_seen_at,
                            func.clock_timestamp(),
                        ),
                    },
                ).returning(AccountRow)
            )
        ).scalar_one()

        normalized_name = last_known_name.lower()
        name_insert = insert(AccountMinecraftNameRow).values(
            name_observation_id=uuid4(),
            account_id=account_row.account_id,
            player_name=last_known_name,
            normalized_name=normalized_name,
            first_seen_at=func.now(),
            last_seen_at=func.now(),
        )
        await self._session.execute(
            name_insert.on_conflict_do_update(
                index_elements=[
                    AccountMinecraftNameRow.account_id,
                    AccountMinecraftNameRow.normalized_name,
                ],
                set_={
                    "player_name": name_insert.excluded.player_name,
                    "last_seen_at": func.greatest(
                        AccountMinecraftNameRow.first_seen_at,
                        AccountMinecraftNameRow.last_seen_at,
                        name_insert.excluded.last_seen_at,
                        func.clock_timestamp(),
                    ),
                },
            )
        )
        return account_from_row(account_row)

    async def lock_account(self, account_id: UUID) -> Account | None:
        row = (
            await self._session.execute(
                select(AccountRow)
                .where(AccountRow.account_id == account_id)
                .with_for_update(of=AccountRow)
            )
        ).scalar_one_or_none()
        return account_from_row(row) if row is not None else None

    async def get_current_life(self, account_id: UUID, *, for_update: bool) -> Life | None:
        statement = select(LifeRow).where(
            LifeRow.account_id == account_id,
            LifeRow.status == "alive",
        )
        if for_update:
            statement = statement.with_for_update(of=LifeRow)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return life_from_row(row) if row is not None else None

    async def get_lives(self, account_id: UUID) -> tuple[Life, ...]:
        rows = (
            await self._session.execute(
                select(LifeRow)
                .where(LifeRow.account_id == account_id)
                .order_by(LifeRow.generation_no)
            )
        ).scalars()
        return tuple(life_from_row(row) for row in rows)

    async def insert_first_life(self, account_id: UUID) -> Life:
        row = LifeRow(
            life_id=uuid4(),
            account_id=account_id,
            generation_no=1,
            status="alive",
        )
        self._session.add(row)
        await self._session.flush()
        return life_from_row(row)

    async def get_spirit_root(self, life_id: UUID) -> SpiritRoot | None:
        row = await self._session.get(LifeSpiritRootRow, life_id)
        return spirit_root_from_row(row) if row is not None else None

    async def insert_spirit_root(self, spirit_root: SpiritRoot) -> bool:
        inserted_life_id = await self._session.scalar(
            insert(LifeSpiritRootRow)
            .values(
                life_id=spirit_root.life_id,
                quality_code=spirit_root.quality_code,
                base_element_codes=list(spirit_root.base_element_codes),
                variant_element_code=spirit_root.variant_element_code,
                generator_version=spirit_root.generator_version,
            )
            .on_conflict_do_nothing(index_elements=[LifeSpiritRootRow.life_id])
            .returning(LifeSpiritRootRow.life_id)
        )
        return inserted_life_id is not None

    async def increment_life_revision(self, life_id: UUID) -> int:
        revision = await self._session.scalar(
            update(LifeRow)
            .where(LifeRow.life_id == life_id, LifeRow.status == "alive")
            .values(revision=LifeRow.revision + 1, updated_at=func.now())
            .returning(LifeRow.revision)
        )
        if revision is None:
            raise RuntimeError("Current life disappeared before revision increment")
        return revision

    async def get_current_life_facts(
        self,
        account_id: UUID,
        *,
        for_update: bool,
    ) -> CurrentLifeQuestFacts | None:
        statement = (
            select(LifeRow, LifeSpiritRootRow)
            .outerjoin(LifeSpiritRootRow, LifeSpiritRootRow.life_id == LifeRow.life_id)
            .where(LifeRow.account_id == account_id, LifeRow.status == "alive")
        )
        if for_update:
            statement = statement.with_for_update(of=LifeRow)
        result = (await self._session.execute(statement)).one_or_none()
        if result is None:
            return None
        life_row, root_row = result
        return CurrentLifeQuestFacts(
            account_id=account_id,
            life_id=life_row.life_id,
            generation_no=life_row.generation_no,
            spirit_root=spirit_root_from_row(root_row) if root_row is not None else None,
            revision=life_row.revision,
        )
