from uuid import UUID, uuid4

from immortal_mmo.player.schemas import Account, Life, SpiritRoot


class InMemoryPlayerRepository:
    def __init__(self) -> None:
        self._accounts_by_id: dict[UUID, Account] = {}
        self._account_ids_by_minecraft_uuid: dict[UUID, UUID] = {}
        self._current_lives_by_account_id: dict[UUID, Life] = {}

    def get_or_create_account(self, minecraft_uuid: UUID, player_name: str) -> Account:
        account_id = self._account_ids_by_minecraft_uuid.get(minecraft_uuid)
        if account_id is not None:
            return self._accounts_by_id[account_id]

        account = Account(
            account_id=uuid4(),
            minecraft_uuid=minecraft_uuid,
            player_name=player_name,
        )
        self._accounts_by_id[account.account_id] = account
        self._account_ids_by_minecraft_uuid[minecraft_uuid] = account.account_id
        return account

    def get_account(self, account_id: UUID) -> Account | None:
        return self._accounts_by_id.get(account_id)

    def get_or_create_current_life(self, account_id: UUID) -> Life:
        existing_life = self._current_lives_by_account_id.get(account_id)
        if existing_life is not None:
            return existing_life

        life = Life(
            life_id=uuid4(),
            account_id=account_id,
            generation_no=1,
            status="alive",
            spirit_root=None,
        )
        self._current_lives_by_account_id[account_id] = life
        return life

    def set_current_life_spirit_root(self, account_id: UUID, spirit_root: SpiritRoot) -> Life:
        life = self._current_lives_by_account_id[account_id]
        updated_life = life.model_copy(update={"spirit_root": spirit_root})
        self._current_lives_by_account_id[account_id] = updated_life
        return updated_life

