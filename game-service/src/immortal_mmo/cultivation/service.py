from dataclasses import asdict
from uuid import UUID

from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.cultivation.progression import project_progress
from immortal_mmo.cultivation.realm_catalog import RealmCatalog
from immortal_mmo.cultivation.schemas import CultivationSnapshotResponse
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError


class CultivationService:
    def __init__(self, uow_factory: UnitOfWorkFactory, realm_catalog: RealmCatalog) -> None:
        self._uow_factory = uow_factory
        self._realm_catalog = realm_catalog

    async def current_life_snapshot(self, account_id: UUID) -> CultivationSnapshotResponse:
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            state = await uow.cultivation.get_or_create_state(life.life_id, for_update=False)
            group_investments = await uow.cultivation.get_group_investments(life.life_id)
            chain = await uow.cultivation.get_active_realm_chain(life.life_id, for_update=False)
            snapshot = project_progress(
                catalog=self._realm_catalog,
                current_level=state.current_level,
                group_investments=group_investments,
                active_entry=chain[-1] if chain else None,
                unrefined_reserve=state.unrefined_cultivation,
                revision=state.revision,
            )
            await uow.commit()
        return CultivationSnapshotResponse(**asdict(snapshot))
