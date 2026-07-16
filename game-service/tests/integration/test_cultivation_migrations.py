from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

EXPECTED_CULTIVATION_TABLES = {
    "life_cultivation_states",
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


@pytest.mark.asyncio
async def test_fresh_schema_contains_complete_cultivation_persistence(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    """
                )
            )
        ).all()
    columns: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        columns.setdefault(table_name, set()).add(column_name)

    assert EXPECTED_CULTIVATION_TABLES <= columns.keys()
    assert {
        "life_id",
        "current_level",
        "unrefined_cultivation",
        "realized_cultivation",
        "active_session_id",
        "revision",
    } <= columns["life_cultivation_states"]
    assert {
        "session_kind",
        "status",
        "idempotency_key",
        "request_fingerprint",
        "frozen_snapshot",
        "cumulative_elapsed_seconds",
        "cumulative_generated",
        "cumulative_reserve_consumed",
        "cumulative_retained",
    } <= columns["cultivation_sessions"]
    assert "selection_order" not in columns["cultivation_session_techniques"]


@pytest.mark.asyncio
async def test_active_session_pointer_is_life_consistent_and_restricted(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(con.oid)
                    FROM pg_constraint AS con
                    JOIN pg_class AS rel ON rel.oid = con.conrelid
                    WHERE rel.relname = 'life_cultivation_states'
                      AND con.conname = 'fk_cultivation_state_active_session'
                    """
                )
            )
        ).scalar_one()

    assert "FOREIGN KEY (life_id, active_session_id)" in row
    assert "REFERENCES cultivation_sessions(life_id, session_id)" in row
    assert "ON DELETE RESTRICT" in row


@pytest.mark.asyncio
async def test_open_sessions_are_unique_per_life(postgres_engine: AsyncEngine) -> None:
    async with postgres_engine.connect() as connection:
        definition = (
            await connection.execute(
                text(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname = 'ux_cultivation_one_open_session'
                    """
                )
            )
        ).scalar_one()

    assert "UNIQUE INDEX" in definition
    assert "life_id" in definition
    assert "pending" in definition
    assert "active" in definition


@pytest.mark.asyncio
async def test_completed_technique_mutation_is_an_explicit_session_shape(
    postgres_engine: AsyncEngine,
) -> None:
    async with postgres_engine.connect() as connection:
        constraints = dict(
            (
                await connection.execute(
                    text(
                        """
                        SELECT con.conname, pg_get_constraintdef(con.oid)
                        FROM pg_constraint AS con
                        JOIN pg_class AS rel ON rel.oid = con.conrelid
                        WHERE rel.relname = 'cultivation_sessions'
                          AND con.conname IN (
                            'ck_cultivation_session_kind',
                            'ck_cultivation_session_shape'
                          )
                        """
                    )
                )
            ).all()
        )
        session_kind_length = (
            await connection.execute(
                text(
                    """
                    SELECT character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'cultivation_sessions'
                      AND column_name = 'session_kind'
                    """
                )
            )
        ).scalar_one()

    assert session_kind_length == 32
    assert "technique_mutation" in constraints["ck_cultivation_session_kind"]
    shape = constraints["ck_cultivation_session_shape"]
    assert "technique_mutation" in shape
    assert "area_id IS NULL" in shape
    assert "target_level IS NULL" in shape
    assert "status" in shape and "completed" in shape
