"""Persist typed quest rewards, physical item identities, and technique learning.

Revision ID: 20260719_004
Revises: 20260718_003
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_004"
down_revision: str | Sequence[str] | None = "20260718_003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quest_reward_grants",
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", sa.String(length=128), nullable=False),
        sa.Column("reward_id", sa.String(length=128), nullable=False),
        sa.Column("reward_type", sa.String(length=32), nullable=False),
        sa.Column("item_code", sa.String(length=128), nullable=True),
        sa.Column("configured_amount", sa.BigInteger(), nullable=False),
        sa.Column("applied_amount", sa.BigInteger(), nullable=False),
        sa.Column("pending_amount", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("grant_id", name="pk_quest_reward_grants"),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["quest_operations.operation_id"],
            name="fk_quest_reward_grants_operation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "quest_id"],
            ["quest_progress.life_id", "quest_progress.quest_id"],
            name="fk_quest_reward_grants_progress",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "operation_id",
            "reward_id",
            name="uq_quest_reward_grants_operation_reward",
        ),
        sa.CheckConstraint(
            "reward_type IN ('fixed_item', 'unrefined_cultivation')",
            name=op.f("ck_quest_reward_grants_type"),
        ),
        sa.CheckConstraint(
            "configured_amount > 0 AND applied_amount >= 0 AND pending_amount >= 0 "
            "AND applied_amount + pending_amount = configured_amount",
            name=op.f("ck_quest_reward_grants_amounts"),
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'pending')",
            name=op.f("ck_quest_reward_grants_status"),
        ),
        sa.CheckConstraint(
            "(reward_type = 'fixed_item' AND item_code IS NOT NULL) OR "
            "(reward_type = 'unrefined_cultivation' AND item_code IS NULL)",
            name=op.f("ck_quest_reward_grants_item_shape"),
        ),
        sa.CheckConstraint(
            "(status = 'applied' AND pending_amount = 0) OR "
            "(status = 'pending' AND pending_amount > 0)",
            name=op.f("ck_quest_reward_grants_status_shape"),
        ),
    )
    op.create_index(
        "ix_quest_reward_grants_life_status",
        "quest_reward_grants",
        ["life_id", "status"],
    )

    op.create_table(
        "item_instances",
        sa.Column("item_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issuance_ordinal", sa.Integer(), nullable=False),
        sa.Column(
            "quest_reward_grant_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("item_code", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("technique_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("location", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("item_instance_id", name="pk_item_instances"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_item_instances_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["quest_reward_grant_id"],
            ["quest_reward_grants.grant_id"],
            name="fk_item_instances_quest_reward_grant",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "issuance_id",
            "issuance_ordinal",
            name="uq_item_instances_issuance",
        ),
        sa.CheckConstraint(
            "definition_version > 0",
            name=op.f("ck_item_instances_definition_version"),
        ),
        sa.CheckConstraint(
            "issuance_ordinal >= 0",
            name=op.f("ck_item_instances_issuance_ordinal"),
        ),
        sa.CheckConstraint(
            "status IN ('pending_delivery', 'owned', 'consumed')",
            name=op.f("ck_item_instances_status"),
        ),
        sa.CheckConstraint(
            "(status = 'pending_delivery' AND location IS NULL "
            "AND delivered_at IS NULL AND consumed_at IS NULL) OR "
            "(status = 'owned' AND location IN ('inventory', 'storage') "
            "AND delivered_at IS NOT NULL AND consumed_at IS NULL) OR "
            "(status = 'consumed' AND location IS NULL AND consumed_at IS NOT NULL)",
            name=op.f("ck_item_instances_state_shape"),
        ),
    )
    op.create_index("ix_item_instances_life_status", "item_instances", ["life_id", "status"])

    op.create_table(
        "quest_cultivation_reward_grants",
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", sa.String(length=128), nullable=False),
        sa.Column("reward_id", sa.String(length=128), nullable=False),
        sa.Column("configured_amount", sa.BigInteger(), nullable=False),
        sa.Column("credited_amount", sa.BigInteger(), nullable=False),
        sa.Column("pending_amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "grant_id",
            name="pk_quest_cultivation_reward_grants",
        ),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_quest_cultivation_reward_grants_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "operation_id",
            "reward_id",
            name="uq_quest_cultivation_reward_operation",
        ),
        sa.CheckConstraint(
            "configured_amount > 0 AND credited_amount >= 0 AND pending_amount >= 0 "
            "AND credited_amount + pending_amount = configured_amount",
            name=op.f("ck_quest_cultivation_reward_amounts"),
        ),
        sa.CheckConstraint(
            "status IN ('applied', 'pending')",
            name=op.f("ck_quest_cultivation_reward_status"),
        ),
        sa.CheckConstraint(
            "(status = 'applied' AND pending_amount = 0) OR "
            "(status = 'pending' AND pending_amount > 0)",
            name=op.f("ck_quest_cultivation_reward_status_shape"),
        ),
    )
    op.create_index(
        "ix_quest_cultivation_reward_pending",
        "quest_cultivation_reward_grants",
        ["life_id", "status"],
    )

    op.create_table(
        "quest_cultivation_reward_claims",
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("applied_amount", sa.BigInteger(), nullable=False),
        sa.Column("pending_amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("response_body", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "operation_id",
            name="pk_quest_cultivation_reward_claims",
        ),
        sa.ForeignKeyConstraint(
            ["grant_id"],
            ["quest_cultivation_reward_grants.grant_id"],
            name="fk_quest_cultivation_reward_claims_grant_id_grants",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_quest_cultivation_reward_claims_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "grant_id",
            "operation_id",
            name="uq_quest_cultivation_reward_claim_grant",
        ),
        sa.CheckConstraint(
            "applied_amount > 0 AND pending_amount >= 0 AND balance_after >= 0",
            name=op.f("ck_quest_cultivation_reward_claim_amounts"),
        ),
    )

    op.create_table(
        "technique_learn_operations",
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("technique_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_body", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("operation_id", name="pk_technique_learn_operations"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_technique_learn_operations_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_instance_id"],
            ["item_instances.item_instance_id"],
            name="fk_technique_learn_operations_item_instance_id_item_instances",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("item_instance_id", name="uq_technique_learn_operations_item"),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_technique_learn_operations_fingerprint"),
        ),
    )

    op.add_column(
        "cultivation_resource_entries",
        sa.Column("quest_reward_grant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cultivation_entries_quest_reward_grant",
        "cultivation_resource_entries",
        "quest_cultivation_reward_grants",
        ["quest_reward_grant_id"],
        ["grant_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        op.f("ck_cultivation_entry_type"),
        "cultivation_resource_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_cultivation_entry_type"),
        "cultivation_resource_entries",
        "entry_type IN ("
        "'combat_reward', 'quest_reward', 'seclusion_consumption', "
        "'seclusion_realization', 'technique_abandonment', 'technique_transfer', "
        "'breakthrough_penalty', 'administrative_adjustment'"
        ")",
    )
    op.drop_constraint(
        op.f("ck_cultivation_combat_source"),
        "cultivation_resource_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_cultivation_reward_source"),
        "cultivation_resource_entries",
        "(entry_type = 'combat_reward' "
        "AND resource_code = 'unrefined_cultivation' AND delta_amount > 0 "
        "AND kill_event_id IS NOT NULL AND quest_reward_grant_id IS NULL) OR "
        "(entry_type = 'quest_reward' "
        "AND resource_code = 'unrefined_cultivation' AND delta_amount > 0 "
        "AND kill_event_id IS NULL AND quest_reward_grant_id IS NOT NULL "
        "AND operation_id IS NOT NULL) OR "
        "(entry_type NOT IN ('combat_reward', 'quest_reward') "
        "AND kill_event_id IS NULL AND quest_reward_grant_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_cultivation_reward_source"),
        "cultivation_resource_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_cultivation_entry_type"),
        "cultivation_resource_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_cultivation_entry_type"),
        "cultivation_resource_entries",
        "entry_type IN ("
        "'combat_reward', 'seclusion_consumption', 'seclusion_realization', "
        "'technique_abandonment', 'technique_transfer', 'breakthrough_penalty', "
        "'administrative_adjustment'"
        ")",
    )
    op.create_check_constraint(
        op.f("ck_cultivation_combat_source"),
        "cultivation_resource_entries",
        "(entry_type = 'combat_reward' "
        "AND resource_code = 'unrefined_cultivation' AND delta_amount > 0 "
        "AND kill_event_id IS NOT NULL) OR "
        "(entry_type <> 'combat_reward' AND kill_event_id IS NULL)",
    )
    op.drop_constraint(
        "fk_cultivation_entries_quest_reward_grant",
        "cultivation_resource_entries",
        type_="foreignkey",
    )
    op.drop_column("cultivation_resource_entries", "quest_reward_grant_id")

    op.drop_table("technique_learn_operations")
    op.drop_table("quest_cultivation_reward_claims")
    op.drop_index(
        "ix_quest_cultivation_reward_pending",
        table_name="quest_cultivation_reward_grants",
    )
    op.drop_table("quest_cultivation_reward_grants")
    op.drop_index("ix_item_instances_life_status", table_name="item_instances")
    op.drop_table("item_instances")
    op.drop_index("ix_quest_reward_grants_life_status", table_name="quest_reward_grants")
    op.drop_table("quest_reward_grants")
