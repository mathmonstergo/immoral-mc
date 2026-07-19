from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory

from immortal_mmo.item.models import ItemInstance, ItemInstanceStatus, ItemLocation
from immortal_mmo.player.service import PlayerService
from immortal_mmo.storage.errors import StorageRevisionConflictError
from immortal_mmo.storage.schemas import StorageMoveRequest
from immortal_mmo.storage.service import StorageService

NOW = datetime(2026, 7, 19, tzinfo=UTC)
AREA = "neutral_training_ground"
OTHER_AREA = "accelerated_cave"


@pytest.mark.asyncio
async def test_storage_isolated_by_area_and_replays_moves() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    players = PlayerService(factory)
    login = await players.login(UUID(int=50_001), "StorageUser")
    life_id = login.current_life.life_id
    item_id = UUID(int=50_002)
    store._state.item_instances[item_id] = ItemInstance(
        item_instance_id=item_id,
        life_id=life_id,
        item_code="technique_manual:GF_YinqiShu_01",
        definition_version=1,
        technique_id="GF_YinqiShu_01",
        issuance_id=UUID(int=50_003),
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.OWNED,
        created_at=NOW,
        delivered_at=NOW,
        consumed_at=None,
        location=ItemLocation.INVENTORY,
    )
    service = StorageService(factory, clock=lambda: NOW)

    empty = await service.snapshot(
        account_id=login.account.account_id,
        area_id=AREA,
        page=1,
    )
    assert empty.revision == 0
    assert empty.slots == []
    assert (
        await service.snapshot(
            account_id=login.account.account_id,
            area_id=OTHER_AREA,
            page=1,
        )
    ).slots == []

    request = StorageMoveRequest(
        move_kind="deposit",
        item_instance_id=item_id,
        expected_revision=0,
        destination_page=1,
        destination_slot=0,
        view_page=1,
    )
    first = await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_004),
        request=request,
    )
    replay = await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_004),
        request=request,
    )

    assert replay == first
    assert first.snapshot.revision == 1
    assert first.snapshot.slots[0].item.item_instance_id == item_id
    assert store._state.item_instances[item_id].location is ItemLocation.STORAGE
    assert (
        await service.snapshot(
            account_id=login.account.account_id,
            area_id=OTHER_AREA,
            page=1,
        )
    ).slots == []


@pytest.mark.asyncio
async def test_storage_rejects_stale_revision_without_mutating_item() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    players = PlayerService(factory)
    login = await players.login(UUID(int=50_011), "StorageStale")
    life_id = login.current_life.life_id
    item_id = UUID(int=50_012)
    store._state.item_instances[item_id] = ItemInstance(
        item_instance_id=item_id,
        life_id=life_id,
        item_code="custom_token",
        definition_version=1,
        technique_id=None,
        issuance_id=UUID(int=50_013),
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.OWNED,
        created_at=NOW,
        delivered_at=NOW,
        consumed_at=None,
        location=ItemLocation.INVENTORY,
    )
    service = StorageService(factory, clock=lambda: NOW)
    await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_014),
        request=StorageMoveRequest(
            move_kind="deposit",
            item_instance_id=item_id,
            expected_revision=0,
            destination_page=1,
            destination_slot=4,
            view_page=1,
        ),
    )

    with pytest.raises(StorageRevisionConflictError):
        await service.move(
            account_id=login.account.account_id,
            area_id=AREA,
            operation_id=UUID(int=50_015),
            request=StorageMoveRequest(
                move_kind="withdraw",
                item_instance_id=item_id,
                expected_revision=0,
                source_page=1,
                source_slot=4,
                view_page=1,
            ),
        )
    assert store._state.item_instances[item_id].location is ItemLocation.STORAGE


@pytest.mark.asyncio
async def test_storage_withdraw_returns_item_to_inventory() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    players = PlayerService(factory)
    login = await players.login(UUID(int=50_021), "StorageWithdraw")
    life_id = login.current_life.life_id
    item_id = UUID(int=50_022)
    store._state.item_instances[item_id] = ItemInstance(
        item_instance_id=item_id,
        life_id=life_id,
        item_code="custom_token",
        definition_version=1,
        technique_id=None,
        issuance_id=UUID(int=50_023),
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.OWNED,
        created_at=NOW,
        delivered_at=NOW,
        consumed_at=None,
        location=ItemLocation.INVENTORY,
    )
    service = StorageService(factory, clock=lambda: NOW)
    await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_024),
        request=StorageMoveRequest(
            move_kind="deposit",
            item_instance_id=item_id,
            expected_revision=0,
            destination_page=1,
            destination_slot=1,
            view_page=1,
        ),
    )
    withdrawn = await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_025),
        request=StorageMoveRequest(
            move_kind="withdraw",
            item_instance_id=item_id,
            expected_revision=1,
            source_page=1,
            source_slot=1,
            view_page=1,
        ),
    )
    assert withdrawn.snapshot.revision == 2
    assert withdrawn.snapshot.slots == []
    assert store._state.item_instances[item_id].location is ItemLocation.INVENTORY


@pytest.mark.asyncio
async def test_storage_snapshot_rejects_item_location_drift() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    login = await PlayerService(factory).login(UUID(int=50_026), "StorageInvariant")
    life_id = login.current_life.life_id
    item_id = UUID(int=50_027)
    store._state.item_instances[item_id] = ItemInstance(
        item_instance_id=item_id,
        life_id=life_id,
        item_code="custom_token",
        definition_version=1,
        technique_id=None,
        issuance_id=UUID(int=50_028),
        issuance_ordinal=0,
        quest_reward_grant_id=None,
        status=ItemInstanceStatus.OWNED,
        created_at=NOW,
        delivered_at=NOW,
        consumed_at=None,
        location=ItemLocation.INVENTORY,
    )
    service = StorageService(factory, clock=lambda: NOW)
    await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_029),
        request=StorageMoveRequest(
            move_kind="deposit",
            item_instance_id=item_id,
            expected_revision=0,
            destination_page=1,
            destination_slot=1,
            view_page=1,
        ),
    )
    stored = store._state.item_instances[item_id]
    store._state.item_instances[item_id] = replace(
        stored,
        location=ItemLocation.INVENTORY,
    )

    with pytest.raises(RuntimeError, match="outside storage"):
        await service.snapshot(
            account_id=login.account.account_id,
            area_id=AREA,
            page=1,
        )


@pytest.mark.asyncio
async def test_storage_move_atomically_swaps_occupied_slots() -> None:
    store = FakeStore()
    factory = FakeUnitOfWorkFactory(store)
    players = PlayerService(factory)
    login = await players.login(UUID(int=50_031), "StorageSwap")
    life_id = login.current_life.life_id
    first_id = UUID(int=50_032)
    second_id = UUID(int=50_033)
    for item_id, issuance_id in (
        (first_id, UUID(int=50_034)),
        (second_id, UUID(int=50_035)),
    ):
        store._state.item_instances[item_id] = ItemInstance(
            item_instance_id=item_id,
            life_id=life_id,
            item_code="custom_token",
            definition_version=1,
            technique_id=None,
            issuance_id=issuance_id,
            issuance_ordinal=0,
            quest_reward_grant_id=None,
            status=ItemInstanceStatus.OWNED,
            created_at=NOW,
            delivered_at=NOW,
            consumed_at=None,
            location=ItemLocation.INVENTORY,
        )
    service = StorageService(factory, clock=lambda: NOW)
    first = await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_036),
        request=StorageMoveRequest(
            move_kind="deposit",
            item_instance_id=first_id,
            expected_revision=0,
            destination_page=1,
            destination_slot=2,
            view_page=1,
        ),
    )
    await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_037),
        request=StorageMoveRequest(
            move_kind="deposit",
            item_instance_id=second_id,
            expected_revision=first.snapshot.revision,
            destination_page=1,
            destination_slot=3,
            view_page=1,
        ),
    )

    swapped = await service.move(
        account_id=login.account.account_id,
        area_id=AREA,
        operation_id=UUID(int=50_038),
        request=StorageMoveRequest(
            move_kind="move",
            item_instance_id=first_id,
            expected_revision=2,
            source_page=1,
            source_slot=2,
            destination_page=1,
            destination_slot=3,
            view_page=1,
        ),
    )

    by_slot = {slot.slot: slot.item.item_instance_id for slot in swapped.snapshot.slots}
    assert swapped.snapshot.revision == 3
    assert by_slot == {2: second_id, 3: first_id}
    assert store._state.item_instances[first_id].location is ItemLocation.STORAGE
    assert store._state.item_instances[second_id].location is ItemLocation.STORAGE
