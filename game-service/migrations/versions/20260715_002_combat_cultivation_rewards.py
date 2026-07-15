"""Add combat kill and cultivation reward persistence.

Revision ID: 20260715_002
Revises: 20260714_001
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260715_002"
down_revision: str | Sequence[str] | None = "20260714_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "life_cultivation_states",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "unrefined_cultivation",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "realized_cultivation",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("life_id", name="pk_life_cultivation_states"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_cultivation_states_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "unrefined_cultivation >= 0",
            name=op.f("ck_life_cultivation_states_unrefined_nonnegative"),
        ),
        sa.CheckConstraint(
            "realized_cultivation >= 0",
            name=op.f("ck_life_cultivation_states_realized_nonnegative"),
        ),
        sa.CheckConstraint(
            "revision > 0",
            name=op.f("ck_life_cultivation_states_revision_positive"),
        ),
    )
    op.create_table(
        "combat_kill_events",
        sa.Column("kill_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("server_id", sa.String(length=64), nullable=False),
        sa.Column("entity_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mob_internal_name", sa.String(length=128), nullable=False),
        sa.Column("mob_level", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("killer_minecraft_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_life_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attribution_kind", sa.String(length=32), nullable=False),
        sa.Column("technique_id", sa.String(length=128), nullable=True),
        sa.Column("cast_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("world_key", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("telemetry", sa.String(length=16), nullable=False),
        sa.Column("detail_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reward_amount", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("kill_event_id", name="pk_combat_kill_events"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_combat_kill_events_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_combat_kill_events_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "source_type",
            "source_event_id",
            name="uq_combat_kill_source",
        ),
        sa.CheckConstraint(
            "source_type = 'mythicmob_death'",
            name=op.f("ck_combat_kill_source_type"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_combat_kill_request_fingerprint"),
        ),
        sa.CheckConstraint("mob_level >= 0", name=op.f("ck_combat_kill_level")),
        sa.CheckConstraint(
            """
            attribution_kind IN (
                'direct', 'projectile', 'damage_over_time', 'summon',
                'trap', 'formation'
            )
            """,
            name=op.f("ck_combat_kill_attribution"),
        ),
        sa.CheckConstraint(
            """
            outcome IN (
                'rewarded', 'not_rewardable', 'account_not_found',
                'current_life_unavailable'
            )
            """,
            name=op.f("ck_combat_kill_outcome"),
        ),
        sa.CheckConstraint(
            "telemetry IN ('compact', 'detailed')",
            name=op.f("ck_combat_kill_telemetry"),
        ),
        sa.CheckConstraint(
            """
            (telemetry = 'compact' AND detail_payload IS NULL)
            OR telemetry = 'detailed'
            """,
            name=op.f("ck_combat_kill_detail"),
        ),
        sa.CheckConstraint(
            """
            (outcome = 'rewarded'
                AND account_id IS NOT NULL
                AND life_id IS NOT NULL
                AND reward_amount IS NOT NULL
                AND reward_amount > 0)
            OR
            (outcome <> 'rewarded' AND reward_amount IS NULL)
            """,
            name=op.f("ck_combat_kill_reward_shape"),
        ),
    )
    op.create_index(
        "ix_combat_kills_life_time",
        "combat_kill_events",
        ["life_id", sa.text("occurred_at DESC")],
        postgresql_where=sa.text("life_id IS NOT NULL"),
    )
    op.create_index(
        "ix_combat_kills_mob_time",
        "combat_kill_events",
        ["mob_internal_name", sa.text("occurred_at DESC")],
    )
    op.create_table(
        "life_mob_kill_counters",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mob_internal_name", sa.String(length=128), nullable=False),
        sa.Column("kill_count", sa.BigInteger(), nullable=False),
        sa.Column("first_killed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_killed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "life_id",
            "mob_internal_name",
            name="pk_life_mob_kill_counters",
        ),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_mob_kill_counters_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kill_count > 0",
            name=op.f("ck_life_mob_kill_counters_count_positive"),
        ),
        sa.CheckConstraint(
            "last_killed_at >= first_killed_at",
            name=op.f("ck_life_mob_kill_time"),
        ),
    )
    op.create_table(
        "cultivation_resource_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resource_code", sa.String(length=32), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta_amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("kill_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("entry_id", name="pk_cultivation_resource_entries"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_cultivation_resource_entries_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["kill_event_id"],
            ["combat_kill_events.kill_event_id"],
            name="fk_cultivation_entries_kill_event",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "resource_code IN ('unrefined_cultivation', 'realized_cultivation')",
            name=op.f("ck_cultivation_resource_code"),
        ),
        sa.CheckConstraint(
            """
            entry_type IN (
                'combat_reward', 'seclusion_consumption',
                'seclusion_realization', 'administrative_adjustment'
            )
            """,
            name=op.f("ck_cultivation_entry_type"),
        ),
        sa.CheckConstraint(
            "delta_amount <> 0",
            name=op.f("ck_cultivation_entry_delta"),
        ),
        sa.CheckConstraint(
            "balance_after >= 0",
            name=op.f("ck_cultivation_entry_balance_nonnegative"),
        ),
        sa.CheckConstraint(
            """
            (entry_type = 'combat_reward'
                AND resource_code = 'unrefined_cultivation'
                AND delta_amount > 0
                AND kill_event_id IS NOT NULL)
            OR
            (entry_type <> 'combat_reward' AND kill_event_id IS NULL)
            """,
            name=op.f("ck_cultivation_combat_source"),
        ),
    )
    op.create_index(
        "ux_cultivation_kill_recipient",
        "cultivation_resource_entries",
        ["kill_event_id", "life_id", "resource_code"],
        unique=True,
        postgresql_where=sa.text("entry_type = 'combat_reward'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_cultivation_kill_recipient",
        table_name="cultivation_resource_entries",
    )
    op.drop_table("cultivation_resource_entries")
    op.drop_table("life_mob_kill_counters")
    op.drop_index("ix_combat_kills_mob_time", table_name="combat_kill_events")
    op.drop_index("ix_combat_kills_life_time", table_name="combat_kill_events")
    op.drop_table("combat_kill_events")
    op.drop_table("life_cultivation_states")
