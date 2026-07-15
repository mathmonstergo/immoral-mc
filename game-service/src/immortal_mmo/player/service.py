from uuid import UUID

from sqlalchemy.exc import DBAPIError

from immortal_mmo.core.errors import ConflictError, NotFoundError
from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.player.mappers import to_login_response, to_spirit_root_schema
from immortal_mmo.player.models import CurrentLifeQuestFacts, SpiritRootGenerator
from immortal_mmo.player.schemas import (
    PlayerLoginResponse,
    SpiritRootDetectionResponse,
)

RETRYABLE_LOGIN_SQLSTATES = {"40001", "40P01"}
RETRYABLE_LOGIN_UNIQUE_CONSTRAINTS = {
    "uq_accounts_minecraft_uuid",
    "uq_life_generation",
    "ux_lives_one_alive_per_account",
}


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
        for attempt in range(2):
            try:
                return await self._login_once(minecraft_uuid, player_name)
            except DBAPIError as error:
                if attempt == 1 or not _is_retryable_login_error(error):
                    raise
        raise AssertionError("login retry loop exhausted")

    async def _login_once(self, minecraft_uuid: UUID, player_name: str) -> PlayerLoginResponse:
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


def _postgres_error_detail(error: BaseException, attribute: str) -> str | None:
    pending: list[BaseException] = [error]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        value = getattr(current, attribute, None)
        if isinstance(value, str):
            return value
        for nested_attribute in ("orig", "__cause__", "__context__"):
            nested = getattr(current, nested_attribute, None)
            if isinstance(nested, BaseException):
                pending.append(nested)
    return None


def _is_retryable_login_error(error: DBAPIError) -> bool:
    sqlstate = _postgres_error_detail(error, "sqlstate") or _postgres_error_detail(
        error, "pgcode"
    )
    if sqlstate in RETRYABLE_LOGIN_SQLSTATES:
        return True
    if sqlstate != "23505":
        return False
    constraint_name = _postgres_error_detail(error, "constraint_name")
    return constraint_name in RETRYABLE_LOGIN_UNIQUE_CONSTRAINTS
