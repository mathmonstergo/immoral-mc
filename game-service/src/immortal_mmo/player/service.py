from uuid import UUID

from immortal_mmo.core.errors import ConflictError, NotFoundError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.player.models import CurrentLifeQuestFacts, SpiritRootGenerator
from immortal_mmo.player.schemas import (
    PlayerLoginResponse,
    SpiritRootDetectionResponse,
    to_login_response,
    to_spirit_root_schema,
)


class PlayerAccountNotFoundError(NotFoundError):
    code = "player.account_not_found"
    message = "Player account was not found."


class PlayerLifecycleError(ConflictError):
    code = "player.lifecycle_unavailable"
    message = "Player has no current life; reincarnation is required."


class PlayerService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        spirit_root_generator: SpiritRootGenerator | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._spirit_root_generator = spirit_root_generator or SpiritRootGenerator()

    async def login(self, minecraft_uuid: UUID, player_name: str) -> PlayerLoginResponse:
        async with self._uow_factory(isolation="read_committed") as uow:
            account = await uow.players.upsert_account(minecraft_uuid, player_name)
            account = await uow.players.lock_account(account.account_id)
            if account is None:
                raise RuntimeError("Account disappeared after upsert")
            life = await uow.players.get_current_life(account.account_id, for_update=True)
            if life is None:
                if await uow.players.get_lives(account.account_id):
                    raise PlayerLifecycleError()
                life = await uow.players.insert_first_life(account.account_id)
            root = await uow.players.get_spirit_root(life.life_id)
            await uow.commit()
            return to_login_response(account, life, root)

    async def detect_current_life_spirit_root(
        self,
        account_id: UUID,
    ) -> SpiritRootDetectionResponse:
        async with self._uow_factory(isolation="read_committed") as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            existing = await uow.players.get_spirit_root(life.life_id)
            if existing is not None:
                await uow.commit()
                return SpiritRootDetectionResponse(
                    life_id=life.life_id,
                    spirit_root=to_spirit_root_schema(existing),
                    already_detected=True,
                )
            generated = self._spirit_root_generator.generate(life.life_id)
            inserted = await uow.players.insert_spirit_root(generated)
            if not inserted:
                generated = await uow.players.get_spirit_root(life.life_id)
                if generated is None:
                    raise RuntimeError("Spirit root insert lost without an existing root")
                already_detected = True
            else:
                await uow.players.increment_life_revision(life.life_id)
                already_detected = False
            await uow.commit()
            return SpiritRootDetectionResponse(
                life_id=life.life_id,
                spirit_root=to_spirit_root_schema(generated),
                already_detected=already_detected,
            )

    async def get_current_life_facts(self, account_id: UUID) -> CurrentLifeQuestFacts:
        async with self._uow_factory(isolation="read_committed") as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            facts = await uow.players.get_current_life_facts(account_id, for_update=False)
            if facts is None:
                raise PlayerLifecycleError()
            await uow.commit()
            return facts
