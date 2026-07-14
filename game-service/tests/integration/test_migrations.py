from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from tests.support.postgres import (
    MigratedPostgres,
    check_migration_metadata,
    downgrade_postgres,
    migrate_postgres,
)

GAMEPLAY_TABLES = {
    "accounts",
    "account_minecraft_names",
    "lives",
    "life_spirit_roots",
    "life_quest_states",
    "quest_progress",
    "quest_operations",
}

EXPECTED_CONSTRAINTS = {
    "accounts": {
        "pk_accounts",
        "uq_accounts_minecraft_uuid",
        "ck_accounts_last_known_name_format",
        "ck_accounts_revision_positive",
    },
    "account_minecraft_names": {
        "pk_account_minecraft_names",
        "fk_account_minecraft_names_account_id_accounts",
        "uq_account_minecraft_name",
        "ck_account_name_seen_order",
        "ck_account_name_format",
        "ck_account_name_normalized",
    },
    "lives": {
        "pk_lives",
        "fk_lives_account_id_accounts",
        "uq_life_generation",
        "uq_life_account",
        "ck_lives_generation_positive",
        "ck_lives_revision_positive",
        "ck_life_status",
        "ck_life_terminal_fields",
        "ck_life_time_order",
    },
    "life_spirit_roots": {
        "pk_life_spirit_roots",
        "fk_life_spirit_roots_life_id_lives",
        "ck_life_spirit_roots_generator_version_positive",
        "ck_spirit_root_quality",
        "ck_spirit_root_shape",
    },
    "life_quest_states": {
        "pk_life_quest_states",
        "fk_life_quest_states_life_id_lives",
        "ck_life_quest_states_revision_nonnegative",
    },
    "quest_progress": {
        "pk_quest_progress",
        "fk_quest_progress_life_id_lives",
        "ck_quest_progress_definition_version_positive",
        "ck_quest_progress_revision_positive",
        "ck_quest_progress_status",
        "ck_quest_progress_completion",
        "ck_quest_progress_time_order",
    },
    "quest_operations": {
        "pk_quest_operations",
        "fk_quest_operations_account_id_accounts",
        "fk_quest_operation_life_account",
        "ck_quest_operation_command",
        "ck_quest_operation_fingerprint",
        "ck_quest_operation_state",
        "ck_quest_operation_content_type",
        "ck_quest_operation_finalization",
    },
}

EXPECTED_INDEXES = {
    "ix_account_names_normalized",
    "ux_lives_one_alive_per_account",
    "ix_quest_progress_active_life",
    "ix_quest_progress_revision",
    "ix_quest_operations_account_created",
}

EXPECTED_FUNCTIONS = {
    "is_valid_spirit_root",
    "prevent_life_delete_or_terminal_mutation",
    "prevent_spirit_root_mutation",
    "prevent_quest_progress_reversal_or_delete",
    "prevent_quest_operation_rewrite_or_delete",
}

EXPECTED_TRIGGERS = {
    "trg_lives_prevent_delete_terminal_mutation",
    "trg_spirit_roots_prevent_update_delete",
    "trg_quest_progress_prevent_reversal_delete",
    "trg_quest_operations_prevent_rewrite_delete",
}


async def _insert_account(session: AsyncSession, *, name: str = "Steve") -> UUID:
    account_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO accounts (account_id, minecraft_uuid, last_known_name)
            VALUES (:account_id, :minecraft_uuid, :last_known_name)
            """
        ),
        {
            "account_id": account_id,
            "minecraft_uuid": uuid4(),
            "last_known_name": name,
        },
    )
    return account_id


async def _insert_life(
    session: AsyncSession,
    account_id: UUID,
    *,
    generation_no: int = 1,
) -> UUID:
    life_id = uuid4()
    await session.execute(
        text(
            """
            INSERT INTO lives (life_id, account_id, generation_no, status)
            VALUES (:life_id, :account_id, :generation_no, 'alive')
            """
        ),
        {"life_id": life_id, "account_id": account_id, "generation_no": generation_no},
    )
    return life_id


async def _assert_integrity_error(
    session: AsyncSession,
    statement: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await session.execute(text(statement), parameters)


async def _assert_database_error(
    session: AsyncSession,
    statement: str,
    parameters: dict[str, object],
) -> None:
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(text(statement), parameters)


@pytest.mark.asyncio
async def test_upgrade_creates_expected_tables_and_head_revision(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        table_names = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = 'public'
                        """
                    )
                )
            ).scalars()
        )
        revision = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()

    assert table_names - {"alembic_version"} == GAMEPLAY_TABLES
    assert "alembic_version" in table_names
    assert revision == "20260714_001"


@pytest.mark.asyncio
async def test_schema_has_exact_named_constraints_and_indexes(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        constraint_rows = (
            await connection.execute(
                text(
                    """
                    SELECT rel.relname AS table_name, con.conname AS constraint_name
                    FROM pg_constraint AS con
                    JOIN pg_class AS rel ON rel.oid = con.conrelid
                    JOIN pg_namespace AS ns ON ns.oid = rel.relnamespace
                    WHERE ns.nspname = 'public'
                    """
                )
            )
        ).all()
        index_rows = (
            await connection.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    """
                )
            )
        ).all()

    by_table: dict[str, set[str]] = {}
    for table_name, constraint_name in constraint_rows:
        by_table.setdefault(table_name, set()).add(constraint_name)
    for table_name, expected in EXPECTED_CONSTRAINTS.items():
        assert by_table[table_name] == expected

    index_definitions = {name: definition for name, definition in index_rows}
    assert EXPECTED_INDEXES <= index_definitions.keys()
    assert "WHERE ((status)::text = 'alive'::text)" in index_definitions[
        "ux_lives_one_alive_per_account"
    ]
    assert "WHERE ((status)::text = 'active'::text)" in index_definitions[
        "ix_quest_progress_active_life"
    ]


@pytest.mark.asyncio
async def test_schema_has_immutable_functions_and_triggers(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        function_rows = (
            await connection.execute(
                text(
                    """
                    SELECT proname, provolatile::text, proparallel::text
                    FROM pg_proc
                    JOIN pg_namespace ON pg_namespace.oid = pg_proc.pronamespace
                    WHERE nspname = 'public'
                    """
                )
            )
        ).all()
        trigger_names = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT tgname
                        FROM pg_trigger
                        JOIN pg_class ON pg_class.oid = pg_trigger.tgrelid
                        JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                        WHERE nspname = 'public' AND NOT tgisinternal
                        """
                    )
                )
            ).scalars()
        )

    functions = {name: (volatility, parallel) for name, volatility, parallel in function_rows}
    assert EXPECTED_FUNCTIONS <= functions.keys()
    assert functions["is_valid_spirit_root"] == ("i", "s")
    assert trigger_names == EXPECTED_TRIGGERS


@pytest.mark.asyncio
async def test_identity_life_and_root_constraints_reject_invalid_rows(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_sessions() as session, session.begin():
        await _assert_integrity_error(
            session,
            """
            INSERT INTO accounts (account_id, minecraft_uuid, last_known_name)
            VALUES (:account_id, :minecraft_uuid, 'not valid!')
            """,
            {"account_id": uuid4(), "minecraft_uuid": uuid4()},
        )
        account_id = await _insert_account(session)
        now = datetime.now(UTC)
        await _assert_integrity_error(
            session,
            """
            INSERT INTO account_minecraft_names (
                name_observation_id, account_id, player_name, normalized_name,
                first_seen_at, last_seen_at
            ) VALUES (:observation_id, :account_id, 'Steve', 'STEVE', :now, :now)
            """,
            {"observation_id": uuid4(), "account_id": account_id, "now": now},
        )
        life_id = await _insert_life(session, account_id)
        await _assert_integrity_error(
            session,
            """
            INSERT INTO lives (life_id, account_id, generation_no, status)
            VALUES (:life_id, :account_id, 2, 'alive')
            """,
            {"life_id": uuid4(), "account_id": account_id},
        )
        await _assert_integrity_error(
            session,
            """
            UPDATE lives SET status = 'reincarnated' WHERE life_id = :life_id
            """,
            {"life_id": life_id},
        )
        for elements in (
            ["wood", "metal"],
            ["metal", "metal"],
            ["metal", "void"],
            ["metal", None],
        ):
            await _assert_integrity_error(
                session,
                """
                INSERT INTO life_spirit_roots (
                    life_id, quality_code, base_element_codes, generator_version
                ) VALUES (:life_id, 'dual', :elements, 1)
                """,
                {"life_id": life_id, "elements": elements},
            )
        await _assert_integrity_error(
            session,
            """
            INSERT INTO life_spirit_roots (
                life_id, quality_code, base_element_codes, variant_element_code,
                generator_version
            ) VALUES (:life_id, 'variant', ARRAY['earth'], 'ice', 1)
            """,
            {"life_id": life_id},
        )


@pytest.mark.asyncio
async def test_valid_life_and_root_insert_then_become_immutable(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_sessions() as session, session.begin():
        account_id = await _insert_account(session, name="Alex")
        life_id = await _insert_life(session, account_id)
        await session.execute(
            text(
                """
                INSERT INTO life_spirit_roots (
                    life_id, quality_code, base_element_codes,
                    variant_element_code, generator_version
                ) VALUES (:life_id, 'variant', ARRAY['metal'], 'thunder', 1)
                """
            ),
            {"life_id": life_id},
        )
        await _assert_database_error(
            session,
            "UPDATE life_spirit_roots SET generator_version = 2 WHERE life_id = :life_id",
            {"life_id": life_id},
        )
        await _assert_database_error(
            session,
            "DELETE FROM life_spirit_roots WHERE life_id = :life_id",
            {"life_id": life_id},
        )
        died_at = datetime.now(UTC) + timedelta(seconds=1)
        await session.execute(
            text(
                """
                UPDATE lives
                SET status = 'reincarnated', died_at = :died_at,
                    death_cause_code = 'red_zone_no_protection', death_zone_id = 'red-1'
                WHERE life_id = :life_id
                """
            ),
            {"life_id": life_id, "died_at": died_at},
        )
        await _assert_database_error(
            session,
            "UPDATE lives SET revision = revision + 1 WHERE life_id = :life_id",
            {"life_id": life_id},
        )
        await _assert_database_error(
            session,
            "DELETE FROM lives WHERE life_id = :life_id",
            {"life_id": life_id},
        )


@pytest.mark.asyncio
async def test_quest_progress_only_allows_advancing_completion(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_sessions() as session, session.begin():
        account_id = await _insert_account(session, name="Questor")
        life_id = await _insert_life(session, account_id)
        accepted_at = datetime.now(UTC)
        completed_at = accepted_at + timedelta(minutes=1)
        await session.execute(
            text(
                """
                INSERT INTO quest_progress (
                    life_id, quest_id, definition_version, status,
                    accepted_at, revision
                ) VALUES (:life_id, 'first-steps', 1, 'active', :accepted_at, 1)
                """
            ),
            {"life_id": life_id, "accepted_at": accepted_at},
        )
        await _assert_database_error(
            session,
            """
            UPDATE quest_progress
            SET quest_id = 'different', status = 'completed',
                completed_at = :completed_at, revision = 2
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id, "completed_at": completed_at},
        )
        await _assert_database_error(
            session,
            """
            UPDATE quest_progress
            SET status = 'completed', completed_at = :completed_at
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id, "completed_at": completed_at},
        )
        await session.execute(
            text(
                """
                UPDATE quest_progress
                SET status = 'completed', completed_at = :completed_at,
                    revision = 2, updated_at = :completed_at
                WHERE life_id = :life_id AND quest_id = 'first-steps'
                """
            ),
            {"life_id": life_id, "completed_at": completed_at},
        )
        await _assert_database_error(
            session,
            """
            UPDATE quest_progress
            SET status = 'active', completed_at = NULL, revision = 3
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id},
        )
        await _assert_database_error(
            session,
            "DELETE FROM quest_progress WHERE life_id = :life_id",
            {"life_id": life_id},
        )


@pytest.mark.asyncio
async def test_quest_operations_require_complete_finalization_and_then_freeze(
    postgres_sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with postgres_sessions() as session, session.begin():
        account_id = await _insert_account(session, name="Operator")
        life_id = await _insert_life(session, account_id)
        operation_id = uuid4()
        fingerprint = "a" * 64
        await _assert_integrity_error(
            session,
            """
            INSERT INTO quest_operations (
                operation_id, account_id, life_id, command, quest_id, provider_id,
                request_fingerprint, state
            ) VALUES (
                :operation_id, :account_id, :life_id, 'accept', 'first-steps',
                'old-man', :fingerprint, 'succeeded'
            )
            """,
            {
                "operation_id": uuid4(),
                "account_id": account_id,
                "life_id": life_id,
                "fingerprint": fingerprint,
            },
        )
        await session.execute(
            text(
                """
                INSERT INTO quest_operations (
                    operation_id, account_id, life_id, command, quest_id, provider_id,
                    request_fingerprint, state
                ) VALUES (
                    :operation_id, :account_id, :life_id, 'accept', 'first-steps',
                    'old-man', :fingerprint, 'processing'
                )
                """
            ),
            {
                "operation_id": operation_id,
                "account_id": account_id,
                "life_id": life_id,
                "fingerprint": fingerprint,
            },
        )
        await _assert_database_error(
            session,
            """
            UPDATE quest_operations
            SET provider_id = 'other', state = 'succeeded', changed = TRUE,
                response_status = 200, response_content_type = 'application/json',
                response_body = :body, response_contract_version = 1,
                finalized_at = now()
            WHERE operation_id = :operation_id
            """,
            {"operation_id": operation_id, "body": b'{"ok":true}'},
        )
        await session.execute(
            text(
                """
                UPDATE quest_operations
                SET state = 'succeeded', changed = TRUE, response_status = 200,
                    response_content_type = 'application/json', response_body = :body,
                    response_contract_version = 1, finalized_at = now()
                WHERE operation_id = :operation_id
                """
            ),
            {"operation_id": operation_id, "body": b'{"ok":true}'},
        )
        await _assert_database_error(
            session,
            "UPDATE quest_operations SET changed = FALSE WHERE operation_id = :operation_id",
            {"operation_id": operation_id},
        )
        await _assert_database_error(
            session,
            "DELETE FROM quest_operations WHERE operation_id = :operation_id",
            {"operation_id": operation_id},
        )
        stored_body = (
            await session.execute(
                text(
                    "SELECT response_body FROM quest_operations WHERE operation_id = :operation_id"
                ),
                {"operation_id": operation_id},
            )
        ).scalar_one()
        assert stored_body == b'{"ok":true}'

        failed_operation_id = uuid4()
        await session.execute(
            text(
                """
                INSERT INTO quest_operations (
                    operation_id, account_id, life_id, command, quest_id, provider_id,
                    request_fingerprint, state
                ) VALUES (
                    :operation_id, :account_id, :life_id, 'turn_in', 'first-steps',
                    'old-man', :fingerprint, 'processing'
                )
                """
            ),
            {
                "operation_id": failed_operation_id,
                "account_id": account_id,
                "life_id": life_id,
                "fingerprint": "b" * 64,
            },
        )
        await session.execute(
            text(
                """
                UPDATE quest_operations
                SET state = 'domain_failed', changed = FALSE, response_status = 409,
                    response_content_type = 'application/json', response_body = :body,
                    response_contract_version = 1, finalized_at = now()
                WHERE operation_id = :operation_id
                """
            ),
            {"operation_id": failed_operation_id, "body": b'{"error":"conflict"}'},
        )


@pytest.mark.asyncio
async def test_postgres_fixture_uses_requested_major_version(
    migrated_postgres: MigratedPostgres,
) -> None:
    assert migrated_postgres.url.startswith("postgresql+asyncpg://")
    assert migrated_postgres.server_version.startswith("17.")


@pytest.mark.asyncio
async def test_orm_metadata_matches_migrated_schema(
    migrated_postgres: MigratedPostgres,
) -> None:
    await asyncio.to_thread(check_migration_metadata, migrated_postgres.url)


@pytest.mark.asyncio
async def test_downgrade_removes_schema_and_upgrade_restores_head(
    migrated_postgres: MigratedPostgres,
) -> None:
    await asyncio.to_thread(downgrade_postgres, migrated_postgres.url, "base")
    try:
        async with migrated_postgres.engine.connect() as connection:
            table_names = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT tablename
                            FROM pg_tables
                            WHERE schemaname = 'public'
                            """
                        )
                    )
                ).scalars()
            )
            function_names = set(
                (
                    await connection.execute(
                        text(
                            """
                            SELECT proname
                            FROM pg_proc
                            JOIN pg_namespace ON pg_namespace.oid = pg_proc.pronamespace
                            WHERE nspname = 'public'
                            """
                        )
                    )
                ).scalars()
            )
        assert table_names == {"alembic_version"}
        assert EXPECTED_FUNCTIONS.isdisjoint(function_names)
    finally:
        await asyncio.to_thread(migrate_postgres, migrated_postgres.url, "head")

    async with migrated_postgres.engine.connect() as connection:
        revision = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()
    assert revision == "20260714_001"
