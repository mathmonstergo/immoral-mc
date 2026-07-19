from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_fresh_schema_contains_reward_and_physical_item_tables(
    postgres_engine: AsyncEngine,
) -> None:
    expected = {
        "quest_reward_grants",
        "item_instances",
        "quest_cultivation_reward_grants",
        "quest_cultivation_reward_claims",
        "technique_learn_operations",
    }
    async with postgres_engine.connect() as connection:
        tables = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """
                    )
                )
            ).scalars()
        )
        resource_columns = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'cultivation_resource_entries'
                        """
                    )
                )
            ).scalars()
        )
        item_columns = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'item_instances'
                        """
                    )
                )
            ).scalars()
        )
    assert expected <= tables
    assert "quest_reward_grant_id" in resource_columns
    assert {"issuance_id", "issuance_ordinal", "quest_reward_grant_id"} <= item_columns
    assert "grant_id" not in item_columns


@pytest.mark.asyncio
async def test_reward_constraints_encode_pending_and_single_use_invariants(
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
                        WHERE rel.relname IN (
                            'quest_reward_grants',
                            'item_instances',
                            'quest_cultivation_reward_grants',
                            'technique_learn_operations',
                            'cultivation_resource_entries'
                        )
                        """
                    )
                )
            ).all()
        )
    assert "pending_amount" in constraints["ck_quest_reward_grants_amounts"]
    assert "pending_delivery" in constraints["ck_item_instances_status"]
    assert "issuance_id" in constraints["uq_item_instances_issuance"]
    assert "quest_reward_grants" in constraints["fk_item_instances_quest_reward_grant"]
    assert "item_instance_id" in constraints["uq_technique_learn_operations_item"]
    assert "quest_reward" in constraints["ck_cultivation_reward_source"]
