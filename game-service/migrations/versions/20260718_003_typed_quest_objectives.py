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
    _backfill_current_layers()
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


def _backfill_current_layers() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT life_technique_id, invested_amount, max_investment,
                   major_realm, current_layer
            FROM life_techniques
            """
        )
    ).mappings()
    for row in rows:
        current_layer = _layer_for_major_realm(
            int(row["invested_amount"]),
            int(row["max_investment"]),
            str(row["major_realm"]),
        )
        if current_layer == row["current_layer"]:
            continue
        connection.execute(
            sa.text(
                """
                UPDATE life_techniques
                SET current_layer = :current_layer, updated_at = now()
                WHERE life_technique_id = :life_technique_id
                """
            ),
            {
                "current_layer": current_layer,
                "life_technique_id": row["life_technique_id"],
            },
        )


# This is intentionally a frozen copy of the curve used when revision 003 was
# authored. Historical migrations must not import mutable domain code: a later
# balance change must never change the result of an old backfill.
_TRANSITION_COUNT = 12
_TECHNIQUE_GROWTH_RATIOS = {
    "练气": (3, 2),
    "筑基": (17, 10),
    "结丹": (9, 5),
    "元婴": (2, 1),
}


def _layer_for_major_realm(
    invested_amount: int,
    capacity: int,
    major_realm: str,
) -> int:
    for value, label in (
        (invested_amount, "invested_amount"),
        (capacity, "capacity"),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
    if invested_amount < 0 or invested_amount > capacity:
        raise ValueError("invested_amount must be within technique capacity")
    if capacity < _TRANSITION_COUNT:
        raise ValueError("capacity must allow twelve positive transition costs")
    try:
        p, q = _TECHNIQUE_GROWTH_RATIOS[major_realm]
    except KeyError as error:
        raise ValueError(f"Unknown technique major realm: {major_realm}") from error
    weights = tuple(
        p**index * q ** (_TRANSITION_COUNT - 1 - index)
        for index in range(_TRANSITION_COUNT)
    )
    total_weight = sum(weights)
    costs = [capacity * weight // total_weight for weight in weights]
    points_left = capacity - sum(costs)
    remainder_order = sorted(
        range(_TRANSITION_COUNT),
        key=lambda index: (-(capacity * weights[index] % total_weight), index),
    )
    for index in remainder_order[:points_left]:
        costs[index] += 1
    if any(cost == 0 for cost in costs):
        raise ValueError("capacity and ratio must produce positive transition costs")
    cumulative = 0
    layer = 1
    for cost in costs:
        cumulative += cost
        if invested_amount < cumulative:
            break
        layer += 1
    return min(layer, _TRANSITION_COUNT + 1)
