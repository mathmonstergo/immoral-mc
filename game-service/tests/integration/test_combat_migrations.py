from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.asyncio
async def test_combat_schema_tables_and_indexes_exist(postgres_engine: AsyncEngine) -> None:
    async with postgres_engine.connect() as connection:
        tables = set(
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
        indexes = set(
            (
                await connection.execute(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                        """
                    )
                )
            ).scalars()
        )

    assert {
        "life_cultivation_states",
        "combat_kill_events",
        "life_mob_kill_counters",
        "cultivation_resource_entries",
    }.issubset(tables)
    assert "ux_cultivation_kill_recipient" in indexes


@pytest.mark.asyncio
async def test_combat_schema_rejects_duplicate_source_event(
    postgres_session,
) -> None:
    account_id = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
    life_id = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
    event_id = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
    await postgres_session.execute(
        text(
            """
            INSERT INTO accounts (account_id, minecraft_uuid, last_known_name)
            VALUES (:account_id, :minecraft_uuid, 'Steve')
            """
        ),
        {
            "account_id": account_id,
            "minecraft_uuid": UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        },
    )
    await postgres_session.execute(
        text(
            """
            INSERT INTO lives (life_id, account_id, generation_no, status)
            VALUES (:life_id, :account_id, 1, 'alive')
            """
        ),
        {"life_id": life_id, "account_id": account_id},
    )
    event = {
        "kill_event_id": UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"),
        "source_type": "mythicmob_death",
        "source_event_id": event_id,
        "server_id": "main-1",
        "entity_uuid": UUID("ffffffff-ffff-4fff-8fff-ffffffffffff"),
        "mob_internal_name": "AzureWolf",
        "mob_level": Decimal("12.000"),
        "killer_minecraft_uuid": UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        "attribution_kind": "damage_over_time",
        "account_id": account_id,
        "life_id": life_id,
        "world_key": "minecraft:overworld",
        "occurred_at": datetime(2026, 7, 15, 12, tzinfo=UTC),
        "outcome": "rewarded",
        "telemetry": "compact",
        "reward_amount": 120,
    }
    await postgres_session.execute(
        text(
            """
            INSERT INTO combat_kill_events (
                kill_event_id, source_type, source_event_id, server_id,
                entity_uuid, mob_internal_name, mob_level,
                killer_minecraft_uuid, attribution_kind, account_id, life_id,
                world_key, occurred_at, outcome, telemetry, reward_amount
            ) VALUES (
                :kill_event_id, :source_type, :source_event_id, :server_id,
                :entity_uuid, :mob_internal_name, :mob_level,
                :killer_minecraft_uuid, :attribution_kind, :account_id, :life_id,
                :world_key, :occurred_at, :outcome, :telemetry, :reward_amount
            )
            """
        ),
        event,
    )
    duplicate = dict(event)
    duplicate["kill_event_id"] = UUID("11111111-1111-4111-8111-111111111111")

    with pytest.raises(IntegrityError) as caught:
        await postgres_session.execute(
            text(
                """
                INSERT INTO combat_kill_events (
                    kill_event_id, source_type, source_event_id, server_id,
                    entity_uuid, mob_internal_name, mob_level,
                    killer_minecraft_uuid, attribution_kind, account_id, life_id,
                    world_key, occurred_at, outcome, telemetry, reward_amount
                ) VALUES (
                    :kill_event_id, :source_type, :source_event_id, :server_id,
                    :entity_uuid, :mob_internal_name, :mob_level,
                    :killer_minecraft_uuid, :attribution_kind, :account_id, :life_id,
                    :world_key, :occurred_at, :outcome, :telemetry, :reward_amount
                )
                """
            ),
            duplicate,
        )
    assert "uq_combat_kill_source" in str(caught.value)
