"""Add typed quest objective progress and item delivery auditing.

Revision ID: 20260718_003
Revises: 20260715_002
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_003"
down_revision: str | Sequence[str] | None = "20260715_002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "quest_objective_progress",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", sa.String(length=128), nullable=False),
        sa.Column("objective_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("objective_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("required_value", sa.BigInteger(), nullable=False),
        sa.Column(
            "current_value",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "life_id",
            "quest_id",
            "objective_id",
            name="pk_quest_objective_progress",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "quest_id"],
            ["quest_progress.life_id", "quest_progress.quest_id"],
            name="fk_quest_objective_progress_quest",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "definition_version > 0",
            name=op.f("ck_quest_objective_progress_definition_version_positive"),
        ),
        sa.CheckConstraint(
            "objective_type = 'mythicmob_kill_count'",
            name=op.f("ck_quest_objective_progress_type"),
        ),
        sa.CheckConstraint(
            "required_value > 0",
            name=op.f("ck_quest_objective_progress_required_positive"),
        ),
        sa.CheckConstraint(
            "current_value >= 0 AND current_value <= required_value",
            name=op.f("ck_quest_objective_progress_current_bounds"),
        ),
    )
    op.create_index(
        "ix_quest_objective_progress_target",
        "quest_objective_progress",
        ["life_id", "objective_type", "target_id"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_quest_objective_progress_reversal_or_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'quest objective progress rows are immutable history';
            END IF;
            IF NEW.life_id IS DISTINCT FROM OLD.life_id
                OR NEW.quest_id IS DISTINCT FROM OLD.quest_id
                OR NEW.objective_id IS DISTINCT FROM OLD.objective_id
                OR NEW.definition_version IS DISTINCT FROM OLD.definition_version
                OR NEW.objective_type IS DISTINCT FROM OLD.objective_type
                OR NEW.target_id IS DISTINCT FROM OLD.target_id
                OR NEW.required_value IS DISTINCT FROM OLD.required_value
                OR NEW.current_value < OLD.current_value THEN
                RAISE EXCEPTION 'quest objective progress cannot be rewritten or reversed';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_quest_objective_progress_prevent_reversal_delete
        BEFORE UPDATE OR DELETE ON quest_objective_progress
        FOR EACH ROW
        EXECUTE FUNCTION prevent_quest_objective_progress_reversal_or_delete()
        """
    )

    op.drop_constraint(
        op.f("ck_item_resource_entry_type"),
        "item_resource_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_item_resource_session_shape"),
        "item_resource_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_item_resource_entry_type"),
        "item_resource_entries",
        "entry_type IN ("
        "'breakthrough_consumption', 'quest_delivery', 'administrative_adjustment'"
        ")",
    )
    op.create_check_constraint(
        op.f("ck_item_resource_session_shape"),
        "item_resource_entries",
        "(entry_type = 'breakthrough_consumption' "
        "AND delta_quantity < 0 AND session_id IS NOT NULL) OR "
        "(entry_type = 'quest_delivery' "
        "AND delta_quantity < 0 AND session_id IS NULL) OR "
        "(entry_type = 'administrative_adjustment' AND session_id IS NULL)",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM quest_objective_progress LIMIT 1)
                OR EXISTS (
                    SELECT 1
                    FROM item_resource_entries
                    WHERE entry_type = 'quest_delivery'
                    LIMIT 1
                ) THEN
                RAISE EXCEPTION
                    'typed quest objective data exists; downgrade would lose authoritative history';
            END IF;
        END;
        $$
        """
    )
    op.drop_constraint(
        op.f("ck_item_resource_session_shape"),
        "item_resource_entries",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_item_resource_entry_type"),
        "item_resource_entries",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_item_resource_entry_type"),
        "item_resource_entries",
        "entry_type IN ('breakthrough_consumption', 'administrative_adjustment')",
    )
    op.create_check_constraint(
        op.f("ck_item_resource_session_shape"),
        "item_resource_entries",
        "(entry_type = 'breakthrough_consumption' AND delta_quantity < 0) OR "
        "(entry_type = 'administrative_adjustment' AND session_id IS NULL)",
    )

    op.execute(
        "DROP TRIGGER trg_quest_objective_progress_prevent_reversal_delete "
        "ON quest_objective_progress"
    )
    op.execute("DROP FUNCTION prevent_quest_objective_progress_reversal_or_delete()")
    op.drop_index(
        "ix_quest_objective_progress_target",
        table_name="quest_objective_progress",
    )
    op.drop_table("quest_objective_progress")
