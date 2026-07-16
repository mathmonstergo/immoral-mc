from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from tests.support.postgres import (
    MigratedPostgres,
    check_migration_metadata,
    rollback_postgres_session,
)

GAMEPLAY_TABLES = {
    "accounts",
    "account_minecraft_names",
    "lives",
    "life_spirit_roots",
    "life_quest_states",
    "quest_progress",
    "quest_operations",
    "life_cultivation_states",
    "combat_kill_events",
    "life_mob_kill_counters",
    "cultivation_resource_entries",
    "life_techniques",
    "technique_investment_entries",
    "life_realm_entries",
    "cultivation_sessions",
    "cultivation_session_techniques",
    "breakthrough_technique_debits",
    "life_item_stacks",
    "item_resource_entries",
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
    "life_cultivation_states": {
        "pk_life_cultivation_states",
        "fk_life_cultivation_states_life_id_lives",
        "fk_cultivation_state_active_session",
        "ck_life_cultivation_states_level",
        "ck_life_cultivation_states_unrefined_nonnegative",
        "ck_life_cultivation_states_realized_nonnegative",
        "ck_life_cultivation_states_revision_positive",
    },
    "combat_kill_events": {
        "pk_combat_kill_events",
        "fk_combat_kill_events_account_id_accounts",
        "fk_combat_kill_events_life_id_lives",
        "uq_combat_kill_source",
        "ck_combat_kill_source_type",
        "ck_combat_kill_request_fingerprint",
        "ck_combat_kill_level",
        "ck_combat_kill_attribution",
        "ck_combat_kill_outcome",
        "ck_combat_kill_telemetry",
        "ck_combat_kill_detail",
        "ck_combat_kill_reward_shape",
    },
    "life_mob_kill_counters": {
        "pk_life_mob_kill_counters",
        "fk_life_mob_kill_counters_life_id_lives",
        "ck_life_mob_kill_counters_count_positive",
        "ck_life_mob_kill_time",
    },
    "cultivation_resource_entries": {
        "pk_cultivation_resource_entries",
        "fk_cultivation_resource_entries_life_id_lives",
        "fk_cultivation_entries_kill_event",
        "ck_cultivation_resource_code",
        "ck_cultivation_entry_type",
        "ck_cultivation_entry_delta",
        "ck_cultivation_entry_balance_nonnegative",
        "ck_cultivation_combat_source",
        "fk_cultivation_entries_session",
        "uq_cultivation_operation_resource",
    },
    "life_techniques": {
        "pk_life_techniques",
        "fk_life_techniques_life_id_lives",
        "uq_life_technique_catalog",
        "uq_life_technique_identity",
        "ck_life_technique_definition_version",
        "ck_life_technique_group",
        "ck_life_technique_major_realm",
        "ck_life_technique_investment",
        "ck_life_technique_layer",
        "ck_life_technique_status",
    },
    "cultivation_sessions": {
        "pk_cultivation_sessions",
        "fk_cultivation_sessions_life_id_lives",
        "uq_cultivation_session_identity",
        "uq_cultivation_session_idempotency",
        "ck_cultivation_session_kind",
        "ck_cultivation_session_status",
        "ck_cultivation_session_fingerprint",
        "ck_cultivation_session_levels",
        "ck_cultivation_session_totals",
        "ck_cultivation_session_times",
        "ck_cultivation_session_shape",
        "ck_cultivation_session_revision",
    },
    "life_realm_entries": {
        "pk_life_realm_entries",
        "fk_life_realm_entries_life_id_lives",
        "fk_life_realm_entries_parent",
        "fk_life_realm_entries_session",
        "uq_life_realm_entry_generation",
        "uq_life_realm_entry_identity",
        "ck_life_realm_entry_generation",
        "ck_life_realm_entry_levels",
        "ck_life_realm_entry_amounts",
        "ck_life_realm_entry_transition",
        "ck_life_realm_entry_status",
        "ck_life_realm_entry_invalidation",
    },
    "cultivation_session_techniques": {
        "pk_cultivation_session_techniques",
        "fk_session_techniques_session",
        "fk_session_techniques_technique",
        "ck_session_technique_definition_version",
        "ck_session_technique_frozen_amounts",
        "ck_session_technique_mastery_seconds",
    },
    "technique_investment_entries": {
        "pk_technique_investment_entries",
        "fk_technique_investment_technique",
        "fk_technique_investment_session",
        "uq_technique_investment_operation",
        "ck_technique_investment_entry_type",
        "ck_technique_investment_delta",
        "ck_technique_investment_balance",
    },
    "breakthrough_technique_debits": {
        "pk_breakthrough_technique_debits",
        "fk_breakthrough_debits_session",
        "fk_breakthrough_debits_technique",
        "ck_breakthrough_debit_amounts",
    },
    "life_item_stacks": {
        "pk_life_item_stacks",
        "fk_life_item_stacks_life_id_lives",
        "ck_life_item_stack_quantity",
        "ck_life_item_stack_revision",
    },
    "item_resource_entries": {
        "pk_item_resource_entries",
        "fk_item_resource_entries_stack",
        "fk_item_resource_entries_session",
        "uq_item_resource_operation",
        "ck_item_resource_entry_type",
        "ck_item_resource_delta",
        "ck_item_resource_balance",
        "ck_item_resource_session_shape",
    },
}

EXPECTED_INDEXES = {
    "ix_account_names_normalized",
    "ux_lives_one_alive_per_account",
    "ix_quest_progress_active_life",
    "ix_quest_progress_revision",
    "ix_quest_operations_account_created",
    "ix_combat_kills_life_time",
    "ix_combat_kills_mob_time",
    "ux_cultivation_kill_recipient",
    "ix_life_techniques_group_status",
    "ux_cultivation_one_open_session",
    "ix_cultivation_sessions_life_created",
    "ix_life_realm_entries_active_chain",
    "ix_technique_investment_life_created",
    "ix_item_resource_life_created",
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

GAME_SERVICE_ROOT = Path(__file__).resolve().parents[2]


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


async def _assert_constraint_violation(
    session: AsyncSession,
    statement: str,
    parameters: dict[str, object],
    *,
    constraint_name: str,
    sqlstate: str = "23514",
) -> None:
    with pytest.raises(IntegrityError) as caught:
        async with session.begin_nested():
            await session.execute(text(statement), parameters)
    assert caught.value.orig.sqlstate == sqlstate
    assert caught.value.orig.__cause__.constraint_name == constraint_name


async def _assert_trigger_rejection(
    session: AsyncSession,
    statement: str,
    parameters: dict[str, object],
    *,
    message: str,
) -> None:
    with pytest.raises(DBAPIError) as caught:
        async with session.begin_nested():
            await session.execute(text(statement), parameters)
    assert caught.value.orig.sqlstate == "P0001"
    assert str(caught.value.orig.__cause__) == message


async def _table_names(connection: AsyncConnection) -> set[str]:
    return set(
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


async def _function_names(connection: AsyncConnection) -> set[str]:
    return set(
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


async def _trigger_names(connection: AsyncConnection) -> set[str]:
    return set(
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


async def _assert_empty_gameplay_data(session: AsyncSession) -> None:
    count = (await session.execute(text("SELECT count(*) FROM accounts"))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_upgrade_creates_expected_tables_and_head_revision(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        table_names = await _table_names(connection)
        revision = (
            await connection.execute(text("SELECT version_num FROM alembic_version"))
        ).scalar_one()

    assert table_names - {"alembic_version"} == GAMEPLAY_TABLES
    assert "alembic_version" in table_names
    assert revision == "20260715_002"


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
                    SELECT indexes.indexname, indexes.indexdef
                    FROM pg_indexes AS indexes
                    JOIN pg_class AS index_rel
                      ON index_rel.relname = indexes.indexname
                    JOIN pg_namespace AS index_ns
                      ON index_ns.oid = index_rel.relnamespace
                     AND index_ns.nspname = indexes.schemaname
                    LEFT JOIN pg_constraint AS constraint_record
                      ON constraint_record.conindid = index_rel.oid
                    WHERE indexes.schemaname = 'public'
                      AND constraint_record.oid IS NULL
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
    assert index_definitions.keys() == EXPECTED_INDEXES
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
        trigger_names = await _trigger_names(connection)

    functions = {name: (volatility, parallel) for name, volatility, parallel in function_rows}
    assert EXPECTED_FUNCTIONS <= functions.keys()
    assert functions["is_valid_spirit_root"] == ("i", "s")
    assert trigger_names == EXPECTED_TRIGGERS


@pytest.mark.asyncio
async def test_identity_life_and_root_constraints_reject_invalid_rows(
    postgres_session: AsyncSession,
) -> None:
    async with postgres_session.begin():
        session = postgres_session
        await _assert_empty_gameplay_data(session)
        await _assert_constraint_violation(
            session,
            """
            INSERT INTO accounts (account_id, minecraft_uuid, last_known_name)
            VALUES (:account_id, :minecraft_uuid, 'not valid!')
            """,
            {"account_id": uuid4(), "minecraft_uuid": uuid4()},
            constraint_name="ck_accounts_last_known_name_format",
        )
        account_id = await _insert_account(session)
        now = datetime.now(UTC)
        await _assert_constraint_violation(
            session,
            """
            INSERT INTO account_minecraft_names (
                name_observation_id, account_id, player_name, normalized_name,
                first_seen_at, last_seen_at
            ) VALUES (:observation_id, :account_id, 'Steve', 'STEVE', :now, :now)
            """,
            {"observation_id": uuid4(), "account_id": account_id, "now": now},
            constraint_name="ck_account_name_normalized",
        )
        life_id = await _insert_life(session, account_id)
        await _assert_constraint_violation(
            session,
            """
            INSERT INTO lives (life_id, account_id, generation_no, status)
            VALUES (:life_id, :account_id, 2, 'alive')
            """,
            {"life_id": uuid4(), "account_id": account_id},
            constraint_name="ux_lives_one_alive_per_account",
            sqlstate="23505",
        )
        await _assert_constraint_violation(
            session,
            """
            UPDATE lives SET status = 'reincarnated' WHERE life_id = :life_id
            """,
            {"life_id": life_id},
            constraint_name="ck_life_terminal_fields",
        )
        for elements in (
            ["wood", "metal"],
            ["metal", "metal"],
            ["metal", "void"],
            ["metal", None],
        ):
            await _assert_constraint_violation(
                session,
                """
                INSERT INTO life_spirit_roots (
                    life_id, quality_code, base_element_codes, generator_version
                ) VALUES (:life_id, 'dual', :elements, 1)
                """,
                {"life_id": life_id, "elements": elements},
                constraint_name="ck_spirit_root_shape",
            )
        await _assert_constraint_violation(
            session,
            """
            INSERT INTO life_spirit_roots (
                life_id, quality_code, base_element_codes, variant_element_code,
                generator_version
            ) VALUES (:life_id, 'variant', ARRAY['earth'], 'ice', 1)
            """,
            {"life_id": life_id},
            constraint_name="ck_spirit_root_shape",
        )


@pytest.mark.asyncio
async def test_valid_life_and_root_insert_then_become_immutable(
    postgres_session: AsyncSession,
) -> None:
    async with postgres_session.begin():
        session = postgres_session
        await _assert_empty_gameplay_data(session)
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
        await _assert_trigger_rejection(
            session,
            "UPDATE life_spirit_roots SET generator_version = 2 WHERE life_id = :life_id",
            {"life_id": life_id},
            message="spirit root is immutable",
        )
        await _assert_trigger_rejection(
            session,
            "DELETE FROM life_spirit_roots WHERE life_id = :life_id",
            {"life_id": life_id},
            message="spirit root is immutable",
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
        await _assert_trigger_rejection(
            session,
            "UPDATE lives SET revision = revision + 1 WHERE life_id = :life_id",
            {"life_id": life_id},
            message="reincarnated life is immutable",
        )
        await _assert_trigger_rejection(
            session,
            "DELETE FROM lives WHERE life_id = :life_id",
            {"life_id": life_id},
            message="life rows are not deleted",
        )


@pytest.mark.asyncio
async def test_quest_progress_only_allows_advancing_completion(
    postgres_session: AsyncSession,
) -> None:
    async with postgres_session.begin():
        session = postgres_session
        await _assert_empty_gameplay_data(session)
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
        await _assert_trigger_rejection(
            session,
            """
            UPDATE quest_progress
            SET quest_id = 'different', status = 'completed',
                completed_at = :completed_at, revision = 2
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id, "completed_at": completed_at},
            message="quest progress identity and acceptance facts are immutable",
        )
        await _assert_trigger_rejection(
            session,
            """
            UPDATE quest_progress
            SET status = 'completed', completed_at = :completed_at
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id, "completed_at": completed_at},
            message="quest progress revision must advance",
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
        await _assert_trigger_rejection(
            session,
            """
            UPDATE quest_progress
            SET status = 'active', completed_at = NULL, revision = 3
            WHERE life_id = :life_id AND quest_id = 'first-steps'
            """,
            {"life_id": life_id},
            message="quest progress only transitions active to completed",
        )
        await _assert_trigger_rejection(
            session,
            "DELETE FROM quest_progress WHERE life_id = :life_id",
            {"life_id": life_id},
            message="quest progress rows are not deleted",
        )


@pytest.mark.asyncio
async def test_quest_operations_require_complete_finalization_and_then_freeze(
    postgres_session: AsyncSession,
) -> None:
    async with postgres_session.begin():
        session = postgres_session
        await _assert_empty_gameplay_data(session)
        account_id = await _insert_account(session, name="Operator")
        life_id = await _insert_life(session, account_id)
        operation_id = uuid4()
        fingerprint = "a" * 64
        await _assert_constraint_violation(
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
            constraint_name="ck_quest_operation_finalization",
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
        await _assert_trigger_rejection(
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
            message="quest operation request identity is immutable",
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
        await _assert_trigger_rejection(
            session,
            "UPDATE quest_operations SET changed = FALSE WHERE operation_id = :operation_id",
            {"operation_id": operation_id},
            message="finalized quest operations are immutable",
        )
        await _assert_trigger_rejection(
            session,
            "DELETE FROM quest_operations WHERE operation_id = :operation_id",
            {"operation_id": operation_id},
            message="quest operation rows are not deleted",
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
        failed_row = (
            await session.execute(
                text(
                    """
                    SELECT state, changed, response_status, response_content_type,
                           response_body, response_contract_version, finalized_at
                    FROM quest_operations
                    WHERE operation_id = :operation_id
                    """
                ),
                {"operation_id": failed_operation_id},
            )
        ).one()
        assert failed_row.state == "domain_failed"
        assert failed_row.changed is False
        assert failed_row.response_status == 409
        assert failed_row.response_content_type == "application/json"
        assert failed_row.response_body == b'{"error":"conflict"}'
        assert failed_row.response_contract_version == 1
        assert failed_row.finalized_at is not None


@pytest.mark.asyncio
async def test_postgres_fixture_uses_requested_major_version(
    migrated_postgres: MigratedPostgres,
) -> None:
    assert migrated_postgres.url.startswith("postgresql+asyncpg://")
    assert migrated_postgres.server_version.startswith("17.")


@pytest.mark.asyncio
async def test_alembic_cli_uses_database_url_from_environment(
    migrated_postgres: MigratedPostgres,
) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = migrated_postgres.url

    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "current"],
        cwd=GAME_SERVICE_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "20260715_002 (head)" in result.stdout


@pytest.mark.asyncio
async def test_rollback_session_does_not_persist_rows(
    postgres_engine: AsyncEngine,
) -> None:
    async with rollback_postgres_session(postgres_engine) as session:
        async with session.begin():
            await _assert_empty_gameplay_data(session)
            await _insert_account(session, name="Transient")

    async with postgres_engine.connect() as connection:
        count = (await connection.execute(text("SELECT count(*) FROM accounts"))).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_orm_metadata_matches_migrated_schema(
    migrated_postgres: MigratedPostgres,
) -> None:
    await asyncio.to_thread(check_migration_metadata, migrated_postgres.url)
