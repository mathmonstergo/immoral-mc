import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.support.fakes import processing_operation

from immortal_mmo.db.uow import SqlAlchemyUnitOfWorkFactory
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
from immortal_mmo.quest.models import QuestProviderDefinition
from immortal_mmo.quest.postgres_repository import PostgresQuestRepository
from immortal_mmo.quest.repository import (
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
async def test_different_operation_accepts_and_turn_ins_change_once_per_transition(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    players, quests, account_id, life_id = await logged_in(postgres_sessions, 103)

    accepts = await asyncio.gather(
        quests.accept(account_id, "first-steps", "old-man", uuid4()),
        quests.accept(account_id, "first-steps", "old-man", uuid4()),
    )
    assert sorted(body(response)["changed"] for response in accepts) == [False, True]
    assert {body(response)["interaction_state"]["revision"]["quest"] for response in accepts} == {
        1
    }

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
    assert len(selects) == 3
    assert sum("quest_progress" in statement for statement in selects) == 1


@pytest.mark.asyncio
async def test_current_life_query_can_use_partial_alive_index_with_history(
    postgres_sessions: async_sessionmaker[AsyncSession],
    clean_postgres_data: None,
) -> None:
    del clean_postgres_data
    _, _, account_id, _ = await logged_in(postgres_sessions, 111)
    async with postgres_sessions.begin() as session:
        for index in range(200):
            other_account_id = uuid4()
            await session.execute(
                text(
                    """
                    INSERT INTO accounts (
                        account_id, minecraft_uuid, last_known_name
                    ) VALUES (:account_id, :minecraft_uuid, :player_name)
                    """
                ),
                {
                    "account_id": other_account_id,
                    "minecraft_uuid": uuid4(),
                    "player_name": f"Hist{index}",
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO lives (
                        life_id, account_id, generation_no, status,
                        died_at, death_cause_code
                    ) VALUES (
                        :life_id, :account_id, 1, 'reincarnated',
                        now(), 'test_history'
                    )
                    """
                ),
                {"life_id": uuid4(), "account_id": other_account_id},
            )
        await session.execute(text("ANALYZE lives"))
        await session.execute(text("SET LOCAL enable_seqscan = off"))
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
        await session.execute(text("RESET enable_seqscan"))

    assert "ux_lives_one_alive_per_account" in "\n".join(plan)
