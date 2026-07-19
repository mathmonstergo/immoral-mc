from datetime import UTC, datetime
from uuid import UUID

from immortal_mmo.core.uow import UnitOfWorkFactory
from immortal_mmo.item.errors import ItemInstanceNotFoundError
from immortal_mmo.item.models import ItemInstance
from immortal_mmo.item.schemas import (
    InventoryItemInstancesResponse,
    ItemDeliveryConfirmationResponse,
    ItemInstanceProjection,
    PendingItemDeliveriesResponse,
)
from immortal_mmo.player.service import PlayerAccountNotFoundError, PlayerLifecycleError


class ItemService:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def pending_deliveries(self, account_id: UUID) -> PendingItemDeliveriesResponse:
        async with self._uow_factory(isolation="repeatable_read") as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            instances = await uow.items.get_pending_instances(life.life_id)
            await uow.rollback()
        return PendingItemDeliveriesResponse(
            life_id=life.life_id,
            items=[_projection(item) for item in instances],
        )

    async def inventory_instances(self, account_id: UUID) -> InventoryItemInstancesResponse:
        async with self._uow_factory(isolation="repeatable_read") as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=False)
            if life is None:
                raise PlayerLifecycleError()
            instances = await uow.items.get_inventory_instances(
                life.life_id,
                for_update=False,
            )
            await uow.rollback()
        return InventoryItemInstancesResponse(
            life_id=life.life_id,
            items=[_projection(item) for item in instances],
        )

    async def confirm_delivery(
        self,
        *,
        account_id: UUID,
        item_instance_id: UUID,
    ) -> ItemDeliveryConfirmationResponse:
        async with self._uow_factory() as uow:
            account = await uow.players.lock_account(account_id)
            if account is None:
                raise PlayerAccountNotFoundError()
            life = await uow.players.get_current_life(account_id, for_update=True)
            if life is None:
                raise PlayerLifecycleError()
            try:
                instance = await uow.items.confirm_delivery(
                    item_instance_id=item_instance_id,
                    life_id=life.life_id,
                    delivered_at=datetime.now(UTC),
                )
            except KeyError as error:
                raise ItemInstanceNotFoundError() from error
            if instance.quest_reward_grant_id is not None:
                pending_amount = await uow.items.count_pending_quest_reward_instances(
                    instance.quest_reward_grant_id
                )
                await uow.quests.update_reward_grant_progress(
                    grant_id=instance.quest_reward_grant_id,
                    pending_amount=pending_amount,
                )
            await uow.commit()
        return ItemDeliveryConfirmationResponse(item=_projection(instance))


def _projection(item: ItemInstance) -> ItemInstanceProjection:
    return ItemInstanceProjection(
        item_instance_id=item.item_instance_id,
        item_code=item.item_code,
        definition_version=item.definition_version,
        technique_id=item.technique_id,
        status=item.status.value,
        location=None if item.location is None else item.location.value,
    )
