import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.support.fakes import processing_operation

from immortal_mmo.combat.postgres_repository import PostgresCombatRepository
from immortal_mmo.cultivation.db_models import LifeCultivationStateRow, LifeTechniqueRow
from immortal_mmo.cultivation.postgres_repository import PostgresCultivationRepository
from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
from immortal_mmo.item.db_models import LifeItemStackRow
from immortal_mmo.item.postgres_repository import PostgresItemRepository
from immortal_mmo.player.db_models import LifeRow
from immortal_mmo.player.postgres_repository import PostgresPlayerRepository
from immortal_mmo.player.service import (
    PlayerAccountNotFoundError,
    PlayerLifecycleError,
    PlayerService,
)
from immortal_mmo.quest.db_models import (
    LifeQuestStateRow,
    QuestOperationRow,
    QuestProgressRow,
)
from immortal_mmo.quest.definitions import QUEST_CATALOG, QuestDefinitionCatalog
from immortal_mmo.quest.models import (
    ItemDeliveryObjectiveDefinition,
    MythicMobKillObjectiveDefinition,
    QuestProviderDefinition,
    RealmLevelObjectiveDefinition,
    TechniqueLayerObjectiveDefinition,
)
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository
from immortal_mmo.quest.progression import QuestEventProgressionService
from immortal_mmo.quest.repository import (
    QuestObjectiveProgress,
    QuestOperationCommand,
    QuestOperationState,
    QuestProgress,
    QuestProgressStatus,
)
from immortal_mmo.quest.service import (
    QuestDefinitionVersionMismatchError,
    QuestIdempotencyConflictError,
    QuestService,
)


def services(
    sessions: async_sessionmaker[AsyncSession],
    *,
    quest_repository: type[PostgresQuestRepository] = PostgresQuestRepository,
) -> tuple[PlayerService, QuestService]:
    factory = SqlAlchemyUnitOfWorkFactory(
        sessions,
        PostgresPlayerRepository,
        quest_repository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    return PlayerService(factory), QuestService(factory)


async def logged_in(
    sessions: async_sessionmaker[AsyncSession],
    suffix: int,
) -> tuple[PlayerService, QuestService, UUID, UUID]:
    players, quests = services(sessions)
    login = await players.login(UUID(int=suffix), f"Quest{suffix}")
    return players, quests, login.account.account_id, login.current_life.life_id


def body(response: object) -> dict:
    return json.loads(response.body)


@pytest.mark.asyncio
async def test_postgres_mixed_objective_quest_completes_and_consumes_delivery(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    now = datetime(2026, 7, 18, 8, tzinfo=UTC)
    player_service, _, account_id, life_id = await logged_in(postgres_sessions, 98)
    del player_service
    template = QUEST_CATALOG.get_quest("first-steps")
    quest = replace(
        template,
        quest_id="mixed-objectives",
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
        objectives=(
            ItemDeliveryObjectiveDefinition("item", "交付筑基丹", "foundation_pill", 1),
            MythicMobKillObjectiveDefinition("kill", "击杀苍狼", "AzureWolf", 1),
            TechniqueLayerObjectiveDefinition("technique", "测试功法二层", "GF_Test", 2),
            RealmLevelObjectiveDefinition("realm", "练气二层", 2),
        ),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(quest,), providers=(provider,))
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    service = QuestService(factory, catalog, clock=lambda: now)
    technique_instance = UUID(int=98_001)
    async with postgres_sessions() as session:
        session.add_all(
            [
                LifeItemStackRow(
                    life_id=life_id,
                    item_code="foundation_pill",
                    quantity=1,
                    revision=1,
                ),
                LifeCultivationStateRow(
                    life_id=life_id,
                    current_level=2,
                    unrefined_cultivation=0,
                    realized_cultivation=15,
                    revision=1,
                ),
                LifeTechniqueRow(
                    life_technique_id=technique_instance,
                    life_id=life_id,
                    technique_id="GF_Test",
                    definition_version=1,
                    group_code="qi",
                    major_realm="练气",
                    invested_amount=15,
                    max_investment=3_765,
                    current_layer=2,
                    status="active",
                ),
            ]
        )
        await session.commit()

    accepted = await service.accept(
        account_id,
        quest.quest_id,
        provider.provider_id,
        UUID(int=98_002),
    )
    assert body(accepted)["quest"]["state"] == "active"
    async with factory() as uow:
        assert await QuestEventProgressionService(catalog).record_mythicmob_kill(
            uow,
            life_id=life_id,
            mob_internal_name="AzureWolf",
            occurred_at=now,
        )
        await uow.commit()

    state = await service.get_interaction_state(account_id, [provider.provider_id])
    assert state.providers[0].quests[0].state == "ready_to_turn_in"
    completed = await service.turn_in(
        account_id,
        quest.quest_id,
        provider.provider_id,
        UUID(int=98_003),
    )
    assert body(completed)["quest"]["state"] == "completed"

    async with postgres_sessions() as session:
        item = await session.get(
            LifeItemStackRow,
            {"life_id": life_id, "item_code": "foundation_pill"},
        )
        entry_type = await session.scalar(
            text(
                "SELECT entry_type FROM item_resource_entries "
                "WHERE operation_id = :operation_id"
            ),
            {"operation_id": UUID(int=98_003)},
        )
    assert item is not None and item.quantity == 0
    assert entry_type == "quest_delivery"


@pytest.mark.asyncio
async def test_postgres_multi_item_shortage_leaves_every_delivery_stack_unchanged(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    now = datetime(2026, 7, 18, 8, tzinfo=UTC)
    player_service, _, account_id, life_id = await logged_in(postgres_sessions, 121)
    del player_service
    template = QUEST_CATALOG.get_quest("first-steps")
    quest = replace(
        template,
        quest_id="multi-item-shortage",
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
        objectives=(
            ItemDeliveryObjectiveDefinition("first", "交付第一种物品", "item_alpha", 2),
            ItemDeliveryObjectiveDefinition("second", "交付第二种物品", "item_beta", 1),
        ),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(quest,), providers=(provider,))
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    service = QuestService(factory, catalog, clock=lambda: now)
    async with postgres_sessions() as session:
        session.add(
            LifeItemStackRow(
                life_id=life_id,
                item_code="item_alpha",
                quantity=2,
                revision=1,
            )
        )
        await session.commit()

    await service.accept(
        account_id,
        quest.quest_id,
        provider.provider_id,
        UUID(int=121_001),
    )
    operation_id = UUID(int=121_002)
    rejected = await service.turn_in(
        account_id,
        quest.quest_id,
        provider.provider_id,
        operation_id,
    )

    async with postgres_sessions() as session:
        alpha = await session.get(
            LifeItemStackRow,
            {"life_id": life_id, "item_code": "item_alpha"},
        )
        delivery_entries = await session.scalar(
            text(
                "SELECT count(*) FROM item_resource_entries "
                "WHERE operation_id = :operation_id AND entry_type = 'quest_delivery'"
            ),
            {"operation_id": operation_id},
        )
    assert rejected.status_code == 409
    assert body(rejected)["error"]["code"] == "quest.not_ready"
    assert alpha is not None and alpha.quantity == 2
    assert delivery_entries == 0


@pytest.mark.asyncio
async def test_multi_item_operation_conflict_leaves_every_delivery_stack_unchanged(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    now = datetime(2026, 7, 18, 8, tzinfo=UTC)
    player_service, _, account_id, life_id = await logged_in(postgres_sessions, 123)
    del player_service
    template = QUEST_CATALOG.get_quest("first-steps")
    quest = replace(
        template,
        quest_id="multi-item-operation-collision",
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
        objectives=(
            ItemDeliveryObjectiveDefinition("first", "交付第一种物品", "item_alpha", 1),
            ItemDeliveryObjectiveDefinition("second", "交付第二种物品", "item_beta", 1),
        ),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(quest,), providers=(provider,))
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    service = QuestService(factory, catalog, clock=lambda: now)
    operation_id = UUID(int=123_001)
    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        await repository.adjust(
            life_id=life_id,
            item_code="item_alpha",
            delta_quantity=1,
            operation_id=UUID(int=123_002),
            occurred_at=now,
        )
        await repository.adjust(
            life_id=life_id,
            item_code="item_beta",
            delta_quantity=1,
            operation_id=operation_id,
            occurred_at=now,
        )
        await session.commit()

    await service.accept(
        account_id,
        quest.quest_id,
        provider.provider_id,
        UUID(int=123_003),
    )
    rejected = await service.turn_in(
        account_id,
        quest.quest_id,
        provider.provider_id,
        operation_id,
    )

    async with postgres_sessions() as session:
        stacks = {
            stack.item_code: stack.quantity
            for stack in (
                await session.scalars(
                    select(LifeItemStackRow).where(
                        LifeItemStackRow.life_id == life_id,
                        LifeItemStackRow.item_code.in_(("item_alpha", "item_beta")),
                    )
                )
            ).all()
        }
        progress = await session.get(QuestProgressRow, (life_id, quest.quest_id))
        delivery_entries = await session.scalar(
            text(
                "SELECT count(*) FROM item_resource_entries "
                "WHERE operation_id = :operation_id AND entry_type = 'quest_delivery'"
            ),
            {"operation_id": operation_id},
        )
    assert rejected.status_code == 409
    assert body(rejected)["error"]["code"] == QuestIdempotencyConflictError.code
    assert stacks == {"item_alpha": 1, "item_beta": 1}
    assert progress is not None and progress.status == "active"
    assert delivery_entries == 0


@pytest.mark.asyncio
async def test_turn_in_rejects_item_operation_id_reused_by_another_command(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    now = datetime(2026, 7, 18, 8, tzinfo=UTC)
    player_service, _, account_id, life_id = await logged_in(postgres_sessions, 122)
    del player_service
    template = QUEST_CATALOG.get_quest("first-steps")
    quest = replace(
        template,
        quest_id="item-operation-collision",
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
        objectives=(ItemDeliveryObjectiveDefinition("item", "交付物品", "foundation_pill", 1),),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(quest,), providers=(provider,))
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    service = QuestService(factory, catalog, clock=lambda: now)
    operation_id = UUID(int=122_001)
    async with postgres_sessions() as session:
        repository = PostgresItemRepository(session)
        await repository.adjust(
            life_id=life_id,
            item_code="foundation_pill",
            delta_quantity=1,
            operation_id=operation_id,
            occurred_at=now,
        )
        await session.commit()

    await service.accept(
        account_id,
        quest.quest_id,
        provider.provider_id,
        UUID(int=122_002),
    )
    rejected = await service.turn_in(
        account_id,
        quest.quest_id,
        provider.provider_id,
        operation_id,
    )

    async with postgres_sessions() as session:
        stack = await session.get(
            LifeItemStackRow,
            {"life_id": life_id, "item_code": "foundation_pill"},
        )
        progress = await session.get(
            QuestProgressRow,
            (life_id, quest.quest_id),
        )
        delivery_entries = await session.scalar(
            text(
                "SELECT count(*) FROM item_resource_entries "
                "WHERE operation_id = :operation_id AND entry_type = 'quest_delivery'"
            ),
            {"operation_id": operation_id},
        )
    assert rejected.status_code == 409
    assert body(rejected)["error"]["code"] == QuestIdempotencyConflictError.code
    assert stack is not None and stack.quantity == 1
    assert progress is not None and progress.status == "active"
    assert delivery_entries == 0


@pytest.mark.asyncio
async def test_event_objective_progress_is_persisted_and_bounded(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, _, _, life_id = await logged_in(postgres_sessions, 99)
    now = datetime.now(UTC)
    async with postgres_sessions() as session:
        repository = PostgresQuestRepository(session)
        assert await repository.insert_progress_if_absent(
            QuestProgress(
                life_id=life_id,
                quest_id="hunt",
                definition_version=1,
                status=QuestProgressStatus.ACTIVE,
                accepted_at=now,
                completed_at=None,
                revision=1,
            )
        )
        await repository.insert_objective_progresses(
            (
                QuestObjectiveProgress(
                    life_id=life_id,
                    quest_id="hunt",
                    objective_id="wolves",
                    definition_version=1,
                    objective_type="mythicmob_kill_count",
                    target_id="AzureWolf",
                    required_value=2,
                    current_value=0,
                    updated_at=now,
                ),
            )
        )
        assert await repository.increment_objective_progress(
            life_id=life_id,
            quest_id="hunt",
            objective_id="wolves",
            required_value=2,
            updated_at=now,
        ) == 1
        assert await repository.increment_objective_progress(
            life_id=life_id,
            quest_id="hunt",
            objective_id="wolves",
            required_value=2,
            updated_at=now,
        ) == 2
        assert (
            await repository.increment_objective_progress(
                life_id=life_id,
                quest_id="hunt",
                objective_id="wolves",
                required_value=2,
                updated_at=now,
            )
            is None
        )
        await session.commit()

    async with postgres_sessions() as session:
        stored = await PostgresQuestRepository(session).get_objective_progresses(
            life_id,
            {"hunt"},
        )
    assert stored[("hunt", "wolves")].current_value == 2


class PausingAcceptQuestRepository(PostgresQuestRepository):
    def __init__(
        self,
        session: AsyncSession,
        accept_holds_revision: asyncio.Event,
        release_accept: asyncio.Event,
        competing_lock_attempted: asyncio.Event,
    ) -> None:
        super().__init__(session)
        self._accept_holds_revision = accept_holds_revision
        self._release_accept = release_accept
        self._competing_lock_attempted = competing_lock_attempted

    async def get_quest_revision(self, life_id: UUID, *, for_update: bool) -> int:
        if for_update and self._accept_holds_revision.is_set():
            self._competing_lock_attempted.set()
        return await super().get_quest_revision(life_id, for_update=for_update)

    async def insert_progress_if_absent(self, progress: QuestProgress) -> bool:
        self._accept_holds_revision.set()
        await self._release_accept.wait()
        return await super().insert_progress_if_absent(progress)


@pytest.mark.asyncio
async def test_kill_waits_for_concurrent_accept_and_counts_after_accept_commits(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    now = datetime(2026, 7, 18, 8, tzinfo=UTC)
    objective = MythicMobKillObjectiveDefinition("kill", "击杀苍狼", "AzureWolf", 2)
    quest = replace(
        QUEST_CATALOG.get_quest("first-steps"),
        quest_id="concurrent-kill",
        objectives=(objective,),
        provider_ids=("objective-master",),
        turn_in_provider_ids=("objective-master",),
    )
    provider = QuestProviderDefinition(
        provider_id="objective-master",
        display_name="任务执事",
        main_quest_ids=(quest.quest_id,),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=(quest,), providers=(provider,))
    accept_holds_revision = asyncio.Event()
    release_accept = asyncio.Event()
    competing_lock_attempted = asyncio.Event()

    def quest_repository(session: AsyncSession) -> PausingAcceptQuestRepository:
        return PausingAcceptQuestRepository(
            session,
            accept_holds_revision,
            release_accept,
            competing_lock_attempted,
        )

    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        quest_repository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    login = await PlayerService(factory).login(UUID(int=124), "Quest124")
    account_id = login.account.account_id
    life_id = login.current_life.life_id
    quests = QuestService(factory, catalog, clock=lambda: now)
    progression = QuestEventProgressionService(catalog)

    async def record_kill() -> bool:
        async with factory() as uow:
            changed = await progression.record_mythicmob_kill(
                uow,
                life_id=life_id,
                mob_internal_name="AzureWolf",
                occurred_at=now,
            )
            await uow.commit()
            return changed

    async with asyncio.TaskGroup() as tasks:
        accept_task = tasks.create_task(
            quests.accept(
                account_id,
                quest.quest_id,
                provider.provider_id,
                UUID(int=124_001),
            )
        )
        await asyncio.wait_for(accept_holds_revision.wait(), timeout=2)
        kill_task = tasks.create_task(record_kill())
        await asyncio.wait_for(competing_lock_attempted.wait(), timeout=2)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(asyncio.shield(kill_task), timeout=0.1)
        release_accept.set()

    assert accept_task.result().status_code == 200
    assert kill_task.result() is True
    async with postgres_sessions() as session:
        stored = await PostgresQuestRepository(session).get_objective_progresses(
            life_id,
            {quest.quest_id},
        )
        revision = await session.scalar(
            select(LifeQuestStateRow.revision).where(LifeQuestStateRow.life_id == life_id)
        )
    assert stored[(quest.quest_id, objective.objective_id)].current_value == 1
    assert revision == 2


@pytest.mark.asyncio
async def test_repository_lazily_locks_revision_and_round_trips_progress_and_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, _, account_id, life_id = await logged_in(postgres_sessions, 100)
    operation_id = uuid4()
    now = datetime.now(UTC)

    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    operation = processing_operation(
        operation_id=operation_id,
        account_id=account_id,
        life_id=life_id,
        command=QuestOperationCommand.ACCEPT,
        quest_id="first-steps",
        provider_id="old-man",
        request_fingerprint="a" * 64,
        created_at=now,
    )
    async with factory() as uow:
        assert await uow.quests.get_quest_revision(life_id, for_update=False) == 0
        assert await uow.quests.get_quest_revision(life_id, for_update=True) == 0
        assert await uow.quests.reserve_operation(operation) is True
        assert await uow.quests.reserve_operation(operation) is False
        assert await uow.quests.insert_progress_if_absent(
            QuestProgress(
                life_id=life_id,
                quest_id="first-steps",
                definition_version=1,
                status=QuestProgressStatus.ACTIVE,
                accepted_at=now,
                completed_at=None,
                revision=1,
            )
        ) is True
        assert await uow.quests.increment_quest_revision(life_id) == 1
        frozen = await uow.quests.finalize_operation(
            operation_id,
            state=QuestOperationState.SUCCEEDED,
            changed=True,
            response_status=200,
            response_content_type="application/json",
            response_body=b'{"exact":"\\u4e2d\\u6587"}',
            response_contract_version=1,
            finalized_at=now,
        )
        await uow.commit()

    restarted = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    async with restarted() as uow:
        stored = await uow.quests.get_operation(operation_id)
        progresses = await uow.quests.get_progresses(life_id, {"first-steps"})
        assert stored == frozen
        assert stored is not None
        assert stored.response_body == b'{"exact":"\\u4e2d\\u6587"}'
        assert progresses["first-steps"].status is QuestProgressStatus.ACTIVE
        assert await uow.quests.get_quest_revision(life_id, for_update=False) == 1


@pytest.mark.asyncio
async def test_repository_revision_read_does_not_insert_aggregate_row(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, _, _, life_id = await logged_in(postgres_sessions, 112)
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )

    async with factory(isolation="repeatable_read") as uow:
        assert await uow.quests.get_quest_revision(life_id, for_update=False) == 0
        await uow.commit()

    async with postgres_sessions() as session:
        assert await session.get(LifeQuestStateRow, life_id) is None


@pytest.mark.asyncio
async def test_same_operation_accept_concurrently_mutates_once_and_replays_exact_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, life_id = await logged_in(postgres_sessions, 101)
    operation_id = uuid4()

    first, second = await asyncio.gather(
        quests.accept(account_id, "first-steps", "old-man", operation_id),
        quests.accept(account_id, "first-steps", "old-man", operation_id),
    )

    assert (first.status_code, first.content_type, first.body) == (
        second.status_code,
        second.content_type,
        second.body,
    )
    assert first.contract_version == second.contract_version == 1
    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(QuestProgressRow)) == 1
        assert await session.scalar(
            select(LifeQuestStateRow.revision).where(LifeQuestStateRow.life_id == life_id)
        ) == 1


@pytest.mark.asyncio
async def test_same_operation_domain_failure_concurrently_replays_exact_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, _ = await logged_in(postgres_sessions, 102)
    operation_id = uuid4()

    first, second = await asyncio.gather(
        quests.turn_in(account_id, "first-steps", "old-man", operation_id),
        quests.turn_in(account_id, "first-steps", "old-man", operation_id),
    )

    assert first.status_code == 409
    assert (first.content_type, first.body) == (second.content_type, second.body)
    assert body(first)["error"]["code"] == "quest.not_accepted"


@pytest.mark.asyncio
async def test_same_operation_turn_in_concurrently_completes_once_and_replays_exact_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, quests, account_id, life_id = await logged_in(postgres_sessions, 116)
    await quests.accept(account_id, "first-steps", "old-man", uuid4())
    await players.detect_current_life_spirit_root(account_id)
    operation_id = uuid4()

    first, second = await asyncio.gather(
        quests.turn_in(account_id, "first-steps", "old-man", operation_id),
        quests.turn_in(account_id, "first-steps", "old-man", operation_id),
    )

    assert first.status_code == second.status_code == 200
    assert first.content_type == second.content_type == "application/json"
    assert first.body == second.body
    assert first.contract_version == second.contract_version == 1
    assert body(first)["changed"] is True

    _, restarted = services(postgres_sessions)
    replayed = await restarted.turn_in(
        account_id,
        "first-steps",
        "old-man",
        operation_id,
    )
    assert (replayed.status_code, replayed.content_type, replayed.body) == (
        first.status_code,
        first.content_type,
        first.body,
    )
    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(QuestProgressRow)) == 1
        progress = await session.get(QuestProgressRow, (life_id, "first-steps"))
        assert progress is not None
        assert progress.status == "completed"
        assert progress.revision == 2
        assert await session.scalar(
            select(LifeQuestStateRow.revision).where(LifeQuestStateRow.life_id == life_id)
        ) == 2


@pytest.mark.asyncio
async def test_same_operation_concurrent_different_accounts_exposes_committed_winner(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, first_account_id, _ = await logged_in(postgres_sessions, 113)
    _, _, second_account_id, _ = await logged_in(postgres_sessions, 114)
    operation_id = uuid4()

    results = await asyncio.gather(
        quests.accept(first_account_id, "first-steps", "old-man", operation_id),
        quests.accept(second_account_id, "first-steps", "old-man", operation_id),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, BaseException) for result in results) == 1
    conflicts = [result for result in results if isinstance(result, BaseException)]
    assert len(conflicts) == 1
    assert isinstance(conflicts[0], QuestIdempotencyConflictError)
    async with postgres_sessions() as session:
        operation = await session.get(QuestOperationRow, operation_id)
        assert operation is not None
        assert operation.state == "succeeded"
        assert await session.scalar(select(func.count()).select_from(QuestProgressRow)) == 1


@pytest.mark.asyncio
async def test_different_operation_accepts_change_once_and_increment_revision_once(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, life_id = await logged_in(postgres_sessions, 103)

    accepts = await asyncio.gather(
        quests.accept(account_id, "first-steps", "old-man", uuid4()),
        quests.accept(account_id, "first-steps", "old-man", uuid4()),
    )
    assert sorted(body(response)["changed"] for response in accepts) == [False, True]
    assert {body(response)["interaction_state"]["revision"]["quest"] for response in accepts} == {
        1
    }
    async with postgres_sessions() as session:
        progress = await session.get(QuestProgressRow, (life_id, "first-steps"))
        assert progress is not None
        assert progress.status == "active"
        assert progress.revision == 1
        assert await session.scalar(
            select(LifeQuestStateRow.revision).where(LifeQuestStateRow.life_id == life_id)
        ) == 1


@pytest.mark.asyncio
async def test_different_operation_turn_ins_change_once_and_increment_revision_once(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, quests, account_id, life_id = await logged_in(postgres_sessions, 117)
    await quests.accept(account_id, "first-steps", "old-man", uuid4())

    await players.detect_current_life_spirit_root(account_id)
    turn_ins = await asyncio.gather(
        quests.turn_in(account_id, "first-steps", "old-man", uuid4()),
        quests.turn_in(account_id, "first-steps", "old-man", uuid4()),
    )
    assert sorted(body(response)["changed"] for response in turn_ins) == [False, True]
    assert {body(response)["interaction_state"]["revision"]["quest"] for response in turn_ins} == {
        2
    }
    completed_accept = await quests.accept(
        account_id,
        "first-steps",
        "old-man",
        uuid4(),
    )
    completed_turn_in = await quests.turn_in(
        account_id,
        "first-steps",
        "old-man",
        uuid4(),
    )
    assert body(completed_accept)["changed"] is False
    assert body(completed_turn_in)["changed"] is False
    assert body(completed_accept)["interaction_state"]["revision"]["quest"] == 2
    assert body(completed_turn_in)["interaction_state"]["revision"]["quest"] == 2
    async with postgres_sessions() as session:
        progress = await session.get(QuestProgressRow, (life_id, "first-steps"))
        assert progress is not None
        assert progress.status == "completed"
        assert progress.revision == 2
        assert await session.scalar(
            select(LifeQuestStateRow.revision).where(LifeQuestStateRow.life_id == life_id)
        ) == 2


@pytest.mark.asyncio
async def test_restart_and_new_life_still_replay_old_global_success_and_failure(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, old_life_id = await logged_in(postgres_sessions, 104)
    success_id = uuid4()
    failure_id = uuid4()
    success = await quests.accept(account_id, "first-steps", "old-man", success_id)
    failure = await quests.turn_in(account_id, "first-steps", "old-man", failure_id)

    new_life_id = uuid4()
    async with postgres_sessions.begin() as session:
        await session.execute(
            text(
                """
                UPDATE lives
                SET status = 'reincarnated', died_at = now(),
                    death_cause_code = 'test_reincarnation'
                WHERE life_id = :life_id
                """
            ),
            {"life_id": old_life_id},
        )
        session.add(
            LifeRow(
                life_id=new_life_id,
                account_id=account_id,
                generation_no=2,
                status="alive",
            )
        )

    _, restarted = services(postgres_sessions)
    replayed_success = await restarted.accept(
        account_id, "first-steps", "old-man", success_id
    )
    replayed_failure = await restarted.turn_in(
        account_id, "first-steps", "old-man", failure_id
    )
    state = await restarted.get_interaction_state(account_id, ["old-man"])

    assert replayed_success == success
    assert replayed_failure == failure
    assert state.life_id == new_life_id
    assert state.revision.quest == 0


class ExplodingQuestRepository(PostgresQuestRepository):
    async def finalize_operation(self, *args, **kwargs):
        del args, kwargs
        raise RuntimeError("injected finalize failure")


@pytest.mark.asyncio
async def test_failure_after_reservation_rolls_back_operation_progress_and_revision(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, quests = services(postgres_sessions, quest_repository=ExplodingQuestRepository)
    login = await players.login(UUID(int=105), "Quest105")

    with pytest.raises(RuntimeError, match="injected finalize failure"):
        await quests.accept(
            login.account.account_id,
            "first-steps",
            "old-man",
            uuid4(),
        )

    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(QuestOperationRow)) == 0
        assert await session.scalar(select(func.count()).select_from(QuestProgressRow)) == 0
        assert await session.scalar(select(func.count()).select_from(LifeQuestStateRow)) == 0


@pytest.mark.asyncio
async def test_account_and_lifecycle_errors_happen_before_operation_reservation(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, life_id = await logged_in(postgres_sessions, 115)

    with pytest.raises(PlayerAccountNotFoundError):
        await quests.accept(uuid4(), "first-steps", "old-man", uuid4())

    async with postgres_sessions.begin() as session:
        await session.execute(
            text(
                """
                UPDATE lives
                SET status = 'reincarnated', died_at = now(),
                    death_cause_code = 'test_reincarnation'
                WHERE life_id = :life_id
                """
            ),
            {"life_id": life_id},
        )
    with pytest.raises(PlayerLifecycleError):
        await quests.accept(account_id, "first-steps", "old-man", uuid4())

    async with postgres_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(QuestOperationRow)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_identity",
    ["account", "command", "quest", "provider", "fingerprint"],
)
async def test_reusing_operation_id_with_any_changed_identity_conflicts_without_rewrite(
    changed_identity: str,
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, _ = await logged_in(postgres_sessions, 106)
    _, _, other_account_id, _ = await logged_in(postgres_sessions, 107)
    operation_id = uuid4()
    original = await quests.accept(account_id, "first-steps", "old-man", operation_id)

    async with postgres_sessions() as session:
        row = await session.get(QuestOperationRow, operation_id)
        assert row is not None
        before = (
            row.account_id,
            row.life_id,
            row.command,
            row.quest_id,
            row.provider_id,
            row.request_fingerprint,
            row.state,
            row.changed,
            row.response_status,
            row.response_content_type,
            bytes(row.response_body),
            row.response_contract_version,
            row.created_at,
            row.finalized_at,
        )

    request_account = other_account_id if changed_identity == "account" else account_id
    request_quest = "different-quest" if changed_identity == "quest" else "first-steps"
    request_provider = "different-provider" if changed_identity == "provider" else "old-man"
    if changed_identity == "fingerprint":
        monkeypatch.setattr(
            QuestService,
            "_fingerprint",
            staticmethod(lambda *args: "f" * 64),
        )

    with pytest.raises(QuestIdempotencyConflictError):
        if changed_identity == "command":
            await quests.turn_in(
                request_account,
                request_quest,
                request_provider,
                operation_id,
            )
        else:
            await quests.accept(
                request_account,
                request_quest,
                request_provider,
                operation_id,
            )
    async with postgres_sessions() as session:
        row = await session.get(QuestOperationRow, operation_id)
        assert row is not None
        after = (
            row.account_id,
            row.life_id,
            row.command,
            row.quest_id,
            row.provider_id,
            row.request_fingerprint,
            row.state,
            row.changed,
            row.response_status,
            row.response_content_type,
            bytes(row.response_body),
            row.response_contract_version,
            row.created_at,
            row.finalized_at,
        )
    assert after == before
    assert original.body == before[10]


@pytest.mark.asyncio
async def test_real_postgres_definition_mismatch_fails_fast_and_is_frozen(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, quests, account_id, life_id = await logged_in(postgres_sessions, 108)
    now = datetime.now(UTC)
    async with postgres_sessions.begin() as session:
        session.add(LifeQuestStateRow(life_id=life_id, revision=1))
        session.add(
            QuestProgressRow(
                life_id=life_id,
                quest_id="first-steps",
                definition_version=999,
                status="active",
                accepted_at=now,
                completed_at=None,
                revision=1,
            )
        )

    operation_id = uuid4()
    first = await quests.accept(account_id, "first-steps", "old-man", operation_id)
    replayed = await quests.accept(account_id, "first-steps", "old-man", operation_id)

    assert first.status_code == 409
    assert body(first)["error"]["code"] == QuestDefinitionVersionMismatchError.code
    assert replayed == first


@pytest.mark.asyncio
async def test_restart_reads_completed_progress_revision_and_exact_success_failure_bytes(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, quests, account_id, life_id = await logged_in(postgres_sessions, 109)
    failure_id = uuid4()
    accept_id = uuid4()
    turn_in_id = uuid4()
    failure = await quests.turn_in(account_id, "first-steps", "old-man", failure_id)
    accepted = await quests.accept(account_id, "first-steps", "old-man", accept_id)
    await players.detect_current_life_spirit_root(account_id)
    completed = await quests.turn_in(account_id, "first-steps", "old-man", turn_in_id)

    _, restarted = services(postgres_sessions)
    state = await restarted.get_interaction_state(account_id, ["old-man"])
    replayed_failure = await restarted.turn_in(
        account_id, "first-steps", "old-man", failure_id
    )
    replayed_accept = await restarted.accept(account_id, "first-steps", "old-man", accept_id)
    replayed_turn_in = await restarted.turn_in(
        account_id, "first-steps", "old-man", turn_in_id
    )

    assert state.life_id == life_id
    assert state.revision.quest == 2
    assert state.providers[0].quests[0].state == "completed"
    assert replayed_failure == failure
    assert replayed_accept == accepted
    assert replayed_turn_in == completed


@pytest.mark.asyncio
async def test_provider_inspection_query_count_is_bounded_independent_of_quest_count(
    postgres_engine: AsyncEngine,
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, _ = services(postgres_sessions)
    login = await players.login(UUID(int=110), "Quest110")
    template = QUEST_CATALOG.get_quest("first-steps")
    quests = tuple(
        replace(
            template,
            quest_id=f"quest-{index}",
            provider_ids=("many",),
            turn_in_provider_ids=("many",),
        )
        for index in range(40)
    )
    provider = QuestProviderDefinition(
        provider_id="many",
        display_name="Many",
        main_quest_ids=tuple(quest.quest_id for quest in quests),
        side_quest_ids=(),
    )
    catalog = QuestDefinitionCatalog(quests=quests, providers=(provider,))
    factory = SqlAlchemyUnitOfWorkFactory(
        postgres_sessions,
        PostgresPlayerRepository,
        PostgresQuestRepository,
        PostgresCombatRepository,
        PostgresCultivationRepository,
        PostgresItemRepository,
    )
    service = QuestService(factory, catalog)
    statements: list[str] = []

    def record_statement(connection, cursor, statement, parameters, context, executemany):
        del connection, cursor, parameters, context, executemany
        statements.append(statement)

    event.listen(postgres_engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        state = await service.get_interaction_state(login.account.account_id, ["many"])
    finally:
        event.remove(postgres_engine.sync_engine, "before_cursor_execute", record_statement)

    selects = [
        statement
        for statement in statements
        if statement.lstrip().upper().startswith("SELECT")
    ]
    assert len(state.providers[0].quests) == 40
    assert len(selects) == 4
    assert sum("quest_progress" in statement for statement in selects) == 1


@pytest.mark.asyncio
async def test_current_life_query_can_use_partial_alive_index_with_history(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, _, account_id, _ = await logged_in(postgres_sessions, 111)
    async with postgres_sessions.begin() as session:
        await session.execute(
            text(
                """
                INSERT INTO accounts (
                    account_id, minecraft_uuid, last_known_name
                )
                SELECT
                    md5('history-account-' || generation)::uuid,
                    md5('history-minecraft-' || generation)::uuid,
                    'Hist' || generation
                FROM generate_series(1, 5000) AS history(generation)
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO lives (
                    life_id, account_id, generation_no, status,
                    died_at, death_cause_code
                )
                SELECT
                    md5('history-life-' || generation)::uuid,
                    md5('history-account-' || generation)::uuid,
                    1,
                    'reincarnated',
                    now(),
                    'test_history'
                FROM generate_series(1, 5000) AS history(generation)
                """
            )
        )
        await session.execute(text("ANALYZE lives"))
        plan = (
            await session.execute(
                text(
                    """
                    EXPLAIN (FORMAT TEXT)
                    SELECT * FROM lives
                    WHERE account_id = :account_id AND status = 'alive'
                    """
                ),
                {"account_id": account_id},
            )
        ).scalars().all()

    assert "ux_lives_one_alive_per_account" in "\n".join(plan)
