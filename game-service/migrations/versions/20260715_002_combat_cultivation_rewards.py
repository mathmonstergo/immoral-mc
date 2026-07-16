"""Add the zero-to-one gameplay persistence baseline.

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
        sa.Column("current_level", sa.SmallInteger(), server_default="1", nullable=False),
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
        sa.Column("active_session_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            "current_level BETWEEN 1 AND 22",
            name=op.f("ck_life_cultivation_states_level"),
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
        "life_techniques",
        sa.Column("life_technique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technique_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("group_code", sa.String(length=32), nullable=False),
        sa.Column("major_realm", sa.String(length=32), nullable=False),
        sa.Column("invested_amount", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("max_investment", sa.BigInteger(), nullable=False),
        sa.Column("current_layer", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column(
            "learned_at",
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
        sa.PrimaryKeyConstraint("life_technique_id", name="pk_life_techniques"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_techniques_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("life_id", "technique_id", name="uq_life_technique_catalog"),
        sa.UniqueConstraint("life_id", "life_technique_id", name="uq_life_technique_identity"),
        sa.CheckConstraint(
            "definition_version > 0",
            name=op.f("ck_life_technique_definition_version"),
        ),
        sa.CheckConstraint(
            "group_code = 'qi' OR group_code ~ '^level:(1[4-9]|2[0-2])$'",
            name=op.f("ck_life_technique_group"),
        ),
        sa.CheckConstraint(
            "major_realm IN ('练气', '筑基', '结丹', '元婴')",
            name=op.f("ck_life_technique_major_realm"),
        ),
        sa.CheckConstraint(
            "max_investment > 0 AND invested_amount BETWEEN 0 AND max_investment",
            name=op.f("ck_life_technique_investment"),
        ),
        sa.CheckConstraint(
            "current_layer BETWEEN 1 AND 13",
            name=op.f("ck_life_technique_layer"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'abandoned')",
            name=op.f("ck_life_technique_status"),
        ),
    )
    op.create_index(
        "ix_life_techniques_group_status",
        "life_techniques",
        ["life_id", "group_code", "status"],
    )
    op.create_table(
        "cultivation_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("area_id", sa.String(length=64), nullable=True),
        sa.Column("content_version", sa.String(length=80), nullable=False),
        sa.Column("source_level", sa.SmallInteger(), nullable=False),
        sa.Column("target_level", sa.SmallInteger(), nullable=True),
        sa.Column("frozen_snapshot", postgresql.JSONB(none_as_null=True), nullable=False),
        sa.Column(
            "cumulative_elapsed_seconds", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("cumulative_generated", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "cumulative_reserve_consumed", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("cumulative_retained", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.BigInteger(), server_default="1", nullable=False),
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
        sa.PrimaryKeyConstraint("session_id", name="pk_cultivation_sessions"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_cultivation_sessions_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("life_id", "session_id", name="uq_cultivation_session_identity"),
        sa.UniqueConstraint(
            "life_id", "idempotency_key", name="uq_cultivation_session_idempotency"
        ),
        sa.CheckConstraint(
            "session_kind IN ('ordinary', 'breakthrough', 'technique_mutation')",
            name=op.f("ck_cultivation_session_kind"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_cultivation_session_status"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_cultivation_session_fingerprint"),
        ),
        sa.CheckConstraint(
            "source_level BETWEEN 1 AND 22 AND "
            "(target_level IS NULL OR target_level BETWEEN 1 AND 22)",
            name=op.f("ck_cultivation_session_levels"),
        ),
        sa.CheckConstraint(
            "cumulative_elapsed_seconds >= 0 AND cumulative_generated >= 0 "
            "AND cumulative_reserve_consumed >= 0 AND cumulative_retained >= 0",
            name=op.f("ck_cultivation_session_totals"),
        ),
        sa.CheckConstraint(
            "completes_at >= started_at AND (settled_at IS NULL OR settled_at >= started_at)",
            name=op.f("ck_cultivation_session_times"),
        ),
        sa.CheckConstraint(
            "(session_kind = 'ordinary' AND area_id IS NOT NULL "
            "AND target_level IS NULL) OR "
            "(session_kind = 'breakthrough' AND area_id IS NULL "
            "AND target_level IS NOT NULL) OR "
            "(session_kind = 'technique_mutation' AND area_id IS NULL "
            "AND target_level IS NULL AND status = 'completed')",
            name=op.f("ck_cultivation_session_shape"),
        ),
        sa.CheckConstraint(
            "revision > 0",
            name=op.f("ck_cultivation_session_revision"),
        ),
    )
    op.create_index(
        "ux_cultivation_one_open_session",
        "cultivation_sessions",
        ["life_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'active')"),
    )
    op.create_index(
        "ix_cultivation_sessions_life_created",
        "cultivation_sessions",
        ["life_id", sa.text("created_at DESC")],
    )
    op.create_foreign_key(
        "fk_cultivation_state_active_session",
        "life_cultivation_states",
        "cultivation_sessions",
        ["life_id", "active_session_id"],
        ["life_id", "session_id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "life_realm_entries",
        sa.Column("realm_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("parent_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_level", sa.SmallInteger(), nullable=False),
        sa.Column("target_level", sa.SmallInteger(), nullable=False),
        sa.Column("source_group", sa.String(length=32), nullable=False),
        sa.Column("target_group", sa.String(length=32), nullable=False),
        sa.Column("source_floor", sa.BigInteger(), nullable=False),
        sa.Column("target_baseline", sa.BigInteger(), nullable=False),
        sa.Column("transition_kind", sa.String(length=24), nullable=False),
        sa.Column("transition_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("realm_entry_id", name="pk_life_realm_entries"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_realm_entries_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "parent_entry_id"],
            ["life_realm_entries.life_id", "life_realm_entries.realm_entry_id"],
            name="fk_life_realm_entries_parent",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "transition_session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_life_realm_entries_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("life_id", "generation", name="uq_life_realm_entry_generation"),
        sa.UniqueConstraint("life_id", "realm_entry_id", name="uq_life_realm_entry_identity"),
        sa.CheckConstraint("generation > 0", name=op.f("ck_life_realm_entry_generation")),
        sa.CheckConstraint(
            "source_level BETWEEN 1 AND 22 AND target_level BETWEEN 1 AND 22 "
            "AND target_level > source_level",
            name=op.f("ck_life_realm_entry_levels"),
        ),
        sa.CheckConstraint(
            "source_floor >= 0 AND target_baseline >= 0",
            name=op.f("ck_life_realm_entry_amounts"),
        ),
        sa.CheckConstraint(
            "transition_kind IN ('adjacent', 'breakthrough', 'failure_advance', 'reentry')",
            name=op.f("ck_life_realm_entry_transition"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'invalidated')",
            name=op.f("ck_life_realm_entry_status"),
        ),
        sa.CheckConstraint(
            "(status = 'active' AND invalidated_at IS NULL) OR "
            "(status = 'invalidated' AND invalidated_at IS NOT NULL)",
            name=op.f("ck_life_realm_entry_invalidation"),
        ),
    )
    op.create_index(
        "ix_life_realm_entries_active_chain",
        "life_realm_entries",
        ["life_id", "generation"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "cultivation_session_techniques",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_technique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("group_code", sa.String(length=32), nullable=False),
        sa.Column("major_realm", sa.String(length=32), nullable=False),
        sa.Column("frozen_capacity", sa.BigInteger(), nullable=False),
        sa.Column("frozen_invested", sa.BigInteger(), nullable=False),
        sa.Column("frozen_full_mastery_seconds", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "session_id", "life_technique_id", name="pk_cultivation_session_techniques"
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_session_techniques_session",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name="fk_session_techniques_technique",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "definition_version > 0", name=op.f("ck_session_technique_definition_version")
        ),
        sa.CheckConstraint(
            "frozen_capacity > 0 AND frozen_invested BETWEEN 0 AND frozen_capacity",
            name=op.f("ck_session_technique_frozen_amounts"),
        ),
        sa.CheckConstraint(
            "frozen_full_mastery_seconds > 0",
            name=op.f("ck_session_technique_mastery_seconds"),
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
        sa.Column("configured_reward_amount", sa.BigInteger(), nullable=True),
        sa.Column("credited_cultivation_amount", sa.BigInteger(), nullable=True),
        sa.Column("unrefined_balance_after", sa.BigInteger(), nullable=True),
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
                AND configured_reward_amount IS NOT NULL
                AND configured_reward_amount > 0
                AND credited_cultivation_amount IS NOT NULL
                AND credited_cultivation_amount >= 0
                AND unrefined_balance_after IS NOT NULL
                AND unrefined_balance_after >= 0)
            OR
            (outcome <> 'rewarded'
                AND configured_reward_amount IS NULL
                AND credited_cultivation_amount IS NULL
                AND unrefined_balance_after IS NULL)
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
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_cultivation_entries_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "operation_id",
            "life_id",
            "resource_code",
            name="uq_cultivation_operation_resource",
        ),
        sa.CheckConstraint(
            "resource_code IN ('unrefined_cultivation', 'realized_cultivation')",
            name=op.f("ck_cultivation_resource_code"),
        ),
        sa.CheckConstraint(
            """
            entry_type IN (
                'combat_reward', 'seclusion_consumption',
                'seclusion_realization', 'technique_abandonment',
                'technique_transfer', 'breakthrough_penalty',
                'administrative_adjustment'
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
    op.create_table(
        "technique_investment_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_technique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta_amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("entry_id", name="pk_technique_investment_entries"),
        sa.ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name="fk_technique_investment_technique",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_technique_investment_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "operation_id", "life_technique_id", name="uq_technique_investment_operation"
        ),
        sa.CheckConstraint(
            "entry_type IN ('seclusion_realization', 'abandonment', "
            "'transfer_in', 'transfer_out', 'breakthrough_penalty', "
            "'administrative_adjustment')",
            name=op.f("ck_technique_investment_entry_type"),
        ),
        sa.CheckConstraint("delta_amount <> 0", name=op.f("ck_technique_investment_delta")),
        sa.CheckConstraint("balance_after >= 0", name=op.f("ck_technique_investment_balance")),
    )
    op.create_index(
        "ix_technique_investment_life_created",
        "technique_investment_entries",
        ["life_id", sa.text("created_at DESC")],
    )
    op.create_table(
        "breakthrough_technique_debits",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_technique_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint(
            "session_id", "life_technique_id", name="pk_breakthrough_technique_debits"
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_breakthrough_debits_session",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name="fk_breakthrough_debits_technique",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "allocated_amount >= 0 AND balance_before >= allocated_amount "
            "AND balance_after = balance_before - allocated_amount",
            name=op.f("ck_breakthrough_debit_amounts"),
        ),
    )
    op.create_table(
        "life_item_stacks",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_code", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default="1", nullable=False),
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
        sa.PrimaryKeyConstraint("life_id", "item_code", name="pk_life_item_stacks"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_item_stacks_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity >= 0", name=op.f("ck_life_item_stack_quantity")),
        sa.CheckConstraint("revision > 0", name=op.f("ck_life_item_stack_revision")),
    )
    op.create_table(
        "item_resource_entries",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_code", sa.String(length=128), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("delta_quantity", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("entry_id", name="pk_item_resource_entries"),
        sa.ForeignKeyConstraint(
            ["life_id", "item_code"],
            ["life_item_stacks.life_id", "life_item_stacks.item_code"],
            name="fk_item_resource_entries_stack",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name="fk_item_resource_entries_session",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("operation_id", "item_code", name="uq_item_resource_operation"),
        sa.CheckConstraint(
            "entry_type IN ('breakthrough_consumption', 'administrative_adjustment')",
            name=op.f("ck_item_resource_entry_type"),
        ),
        sa.CheckConstraint("delta_quantity <> 0", name=op.f("ck_item_resource_delta")),
        sa.CheckConstraint("balance_after >= 0", name=op.f("ck_item_resource_balance")),
        sa.CheckConstraint(
            "(entry_type = 'breakthrough_consumption' AND delta_quantity < 0) OR "
            "(entry_type = 'administrative_adjustment' AND session_id IS NULL)",
            name=op.f("ck_item_resource_session_shape"),
        ),
    )
    op.create_index(
        "ix_item_resource_life_created",
        "item_resource_entries",
        ["life_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_item_resource_life_created", table_name="item_resource_entries")
    op.drop_table("item_resource_entries")
    op.drop_table("life_item_stacks")
    op.drop_table("breakthrough_technique_debits")
    op.drop_index(
        "ix_technique_investment_life_created",
        table_name="technique_investment_entries",
    )
    op.drop_table("technique_investment_entries")
    op.drop_index(
        "ux_cultivation_kill_recipient",
        table_name="cultivation_resource_entries",
    )
    op.drop_table("cultivation_resource_entries")
    op.drop_table("life_mob_kill_counters")
    op.drop_index("ix_combat_kills_mob_time", table_name="combat_kill_events")
    op.drop_index("ix_combat_kills_life_time", table_name="combat_kill_events")
    op.drop_table("combat_kill_events")
    op.drop_table("cultivation_session_techniques")
    op.drop_index("ix_life_realm_entries_active_chain", table_name="life_realm_entries")
    op.drop_table("life_realm_entries")
    op.drop_constraint(
        "fk_cultivation_state_active_session",
        "life_cultivation_states",
        type_="foreignkey",
    )
    op.drop_index("ix_cultivation_sessions_life_created", table_name="cultivation_sessions")
    op.drop_index("ux_cultivation_one_open_session", table_name="cultivation_sessions")
    op.drop_table("cultivation_sessions")
    op.drop_index("ix_life_techniques_group_status", table_name="life_techniques")
    op.drop_table("life_techniques")
    op.drop_table("life_cultivation_states")
