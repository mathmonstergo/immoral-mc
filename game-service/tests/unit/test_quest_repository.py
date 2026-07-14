from uuid import UUID

import pytest
from tests.support.fakes import FakeStore, FakeUnitOfWorkFactory, processing_operation

from immortal_mmo.quest.repository import QuestOperationCommand


@pytest.mark.asyncio
async def test_fake_unit_of_work_rolls_back_uncommitted_state() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    async with factory() as uow:
        await uow.players.upsert_account(UUID(int=1), "Rollback")

    async with factory() as uow:
        assert await uow.players.lock_account(UUID(int=1)) is None


@pytest.mark.asyncio
async def test_fake_unit_of_work_commits_atomically_and_operations_are_global() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    account_id = UUID(int=2)
    life_id = UUID(int=3)
    operation_id = UUID(int=4)
    operation = processing_operation(
        operation_id=operation_id,
        account_id=account_id,
        life_id=life_id,
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        request_fingerprint="a" * 64,
    )

    async with factory() as uow:
        assert await uow.quests.reserve_operation(operation) is True
        await uow.commit()

    async with factory() as uow:
        assert await uow.quests.get_operation(operation_id) == operation
        assert await uow.quests.reserve_operation(operation) is False


@pytest.mark.asyncio
async def test_commit_publishes_a_detached_snapshot_and_closes_the_unit_of_work() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    first_uuid = UUID(int=10)
    second_uuid = UUID(int=11)

    async with factory() as uow:
        first = await uow.players.upsert_account(first_uuid, "First")
        await uow.commit()
        with pytest.raises(RuntimeError, match="closed"):
            await uow.players.upsert_account(second_uuid, "Second")
        with pytest.raises(RuntimeError, match="closed"):
            await uow.commit()

    async with factory() as uow:
        assert await uow.players.lock_account(first.account_id) == first
        assert second_uuid not in uow._working_state.account_ids_by_minecraft_uuid


@pytest.mark.asyncio
async def test_rollback_discards_and_closes_state_that_cannot_later_commit() -> None:
    factory = FakeUnitOfWorkFactory(FakeStore())
    minecraft_uuid = UUID(int=12)

    async with factory() as uow:
        account = await uow.players.upsert_account(minecraft_uuid, "Rollback")
        await uow.rollback()
        with pytest.raises(RuntimeError, match="closed"):
            await uow.players.lock_account(account.account_id)
        with pytest.raises(RuntimeError, match="closed"):
            await uow.commit()

    async with factory() as uow:
        assert await uow.players.lock_account(account.account_id) is None
