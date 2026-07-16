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
        "request_fingerprint": "a" * 64,
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
        "configured_reward_amount": 120,
        "credited_cultivation_amount": 120,
        "unrefined_balance_after": 120,
    }
    await postgres_session.execute(
        text(
            """
            INSERT INTO combat_kill_events (
                kill_event_id, source_type, source_event_id, request_fingerprint, server_id,
                entity_uuid, mob_internal_name, mob_level,
                killer_minecraft_uuid, attribution_kind, account_id, life_id,
                world_key, occurred_at, outcome, telemetry,
                configured_reward_amount, credited_cultivation_amount,
                unrefined_balance_after
            ) VALUES (
                :kill_event_id, :source_type, :source_event_id, :request_fingerprint, :server_id,
                :entity_uuid, :mob_internal_name, :mob_level,
                :killer_minecraft_uuid, :attribution_kind, :account_id, :life_id,
                :world_key, :occurred_at, :outcome, :telemetry,
                :configured_reward_amount, :credited_cultivation_amount,
                :unrefined_balance_after
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
                    kill_event_id, source_type, source_event_id, request_fingerprint, server_id,
                    entity_uuid, mob_internal_name, mob_level,
                    killer_minecraft_uuid, attribution_kind, account_id, life_id,
                    world_key, occurred_at, outcome, telemetry,
                    configured_reward_amount, credited_cultivation_amount,
                    unrefined_balance_after
                ) VALUES (
                    :kill_event_id, :source_type, :source_event_id,
                    :request_fingerprint, :server_id,
                    :entity_uuid, :mob_internal_name, :mob_level,
                    :killer_minecraft_uuid, :attribution_kind, :account_id, :life_id,
                    :world_key, :occurred_at, :outcome, :telemetry,
                    :configured_reward_amount, :credited_cultivation_amount,
                    :unrefined_balance_after
                )
                """
            ),
            duplicate,
        )
    assert "uq_combat_kill_source" in str(caught.value)


@pytest.mark.asyncio
async def test_combat_schema_accepts_untrusted_source_life_without_foreign_key(
    postgres_session,
) -> None:
    result = await postgres_session.execute(
        text(
            """
            INSERT INTO combat_kill_events (
                kill_event_id, source_type, source_event_id, request_fingerprint,
                server_id, entity_uuid, mob_internal_name, mob_level,
                killer_minecraft_uuid, source_life_id, attribution_kind,
                world_key, occurred_at, outcome, telemetry
            ) VALUES (
                :kill_event_id, 'mythicmob_death', :source_event_id, :request_fingerprint,
                'main-1', :entity_uuid, 'AzureWolf', 12.000,
                :killer_uuid, :source_life_id, 'direct',
                'minecraft:overworld', :occurred_at, 'not_rewardable', 'compact'
            )
            """
        ),
        {
            "kill_event_id": UUID("11111111-1111-4111-8111-111111111111"),
            "source_event_id": UUID("22222222-2222-4222-8222-222222222222"),
            "request_fingerprint": "b" * 64,
            "entity_uuid": UUID("33333333-3333-4333-8333-333333333333"),
            "killer_uuid": UUID("44444444-4444-4444-8444-444444444444"),
            "source_life_id": UUID("55555555-5555-4555-8555-555555555555"),
            "occurred_at": datetime(2026, 7, 15, 12, tzinfo=UTC),
        },
    )

    assert result.rowcount == 1


@pytest.mark.asyncio
async def test_combat_schema_rejects_removed_fallback_attribution(
    postgres_session,
) -> None:
    with pytest.raises(IntegrityError) as caught:
        await postgres_session.execute(
            text(
                """
                INSERT INTO combat_kill_events (
                    kill_event_id, source_type, source_event_id, request_fingerprint,
                    server_id, entity_uuid, mob_internal_name, mob_level,
                    killer_minecraft_uuid, attribution_kind,
                    world_key, occurred_at, outcome, telemetry
                ) VALUES (
                    :kill_event_id, 'mythicmob_death', :source_event_id,
                    :request_fingerprint, 'main-1', :entity_uuid, 'AzureWolf', 12.000,
                    :killer_uuid, 'bukkit_fallback',
                    'minecraft:overworld', :occurred_at, 'not_rewardable', 'compact'
                )
                """
            ),
            {
                "kill_event_id": UUID("66666666-6666-4666-8666-666666666666"),
                "source_event_id": UUID("77777777-7777-4777-8777-777777777777"),
                "request_fingerprint": "c" * 64,
                "entity_uuid": UUID("88888888-8888-4888-8888-888888888888"),
                "killer_uuid": UUID("99999999-9999-4999-8999-999999999999"),
                "occurred_at": datetime(2026, 7, 15, 12, tzinfo=UTC),
            },
        )

    assert "ck_combat_kill_attribution" in str(caught.value)
