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
