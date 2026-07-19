"""Add current-life, area-isolated paged storage.

Revision ID: 20260719_005
Revises: 20260719_004
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260719_005"
down_revision: str | Sequence[str] | None = "20260719_004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_item_instances_identity_life",
        "item_instances",
        ["item_instance_id", "life_id"],
    )

    op.create_table(
        "regional_storage_containers",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", sa.String(length=128), nullable=False),
        sa.Column("page_count", sa.SmallInteger(), nullable=False),
        sa.Column("item_slots_per_page", sa.SmallInteger(), nullable=False),
        sa.Column(
            "revision",
            sa.BigInteger(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint(
            "life_id",
            "area_id",
            name="pk_regional_storage_containers",
        ),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_regional_storage_containers_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "area_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'",
            name=op.f("ck_regional_storage_containers_area_id"),
        ),
        sa.CheckConstraint(
            "page_count BETWEEN 1 AND 100",
            name=op.f("ck_regional_storage_containers_page_count"),
        ),
        sa.CheckConstraint(
            "item_slots_per_page BETWEEN 1 AND 45",
            name=op.f("ck_regional_storage_containers_item_slots"),
        ),
        sa.CheckConstraint(
            "revision >= 0",
            name=op.f("ck_regional_storage_containers_revision"),
        ),
    )

    op.create_table(
        "regional_storage_slots",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", sa.String(length=128), nullable=False),
        sa.Column("page", sa.SmallInteger(), nullable=False),
        sa.Column("slot", sa.SmallInteger(), nullable=False),
        sa.Column("item_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.PrimaryKeyConstraint(
            "life_id",
            "area_id",
            "page",
            "slot",
            name="pk_regional_storage_slots",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "area_id"],
            [
                "regional_storage_containers.life_id",
                "regional_storage_containers.area_id",
            ],
            name="fk_regional_storage_slots_container",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_instance_id", "life_id"],
            ["item_instances.item_instance_id", "item_instances.life_id"],
            name="fk_regional_storage_slots_item_life",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "item_instance_id",
            name="uq_regional_storage_slots_item_instance",
        ),
        sa.CheckConstraint(
            "page > 0",
            name=op.f("ck_regional_storage_slots_page"),
        ),
        sa.CheckConstraint(
            "slot BETWEEN 0 AND 44",
            name=op.f("ck_regional_storage_slots_slot"),
        ),
    )
    op.create_index(
        "ix_regional_storage_slots_item_instance",
        "regional_storage_slots",
        ["item_instance_id"],
    )

    op.create_table(
        "regional_storage_operations",
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("area_id", sa.String(length=128), nullable=False),
        sa.Column("move_kind", sa.String(length=16), nullable=False),
        sa.Column("item_instance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_revision", sa.BigInteger(), nullable=False),
        sa.Column("resulting_revision", sa.BigInteger(), nullable=False),
        sa.Column("source_page", sa.SmallInteger(), nullable=True),
        sa.Column("source_slot", sa.SmallInteger(), nullable=True),
        sa.Column("destination_page", sa.SmallInteger(), nullable=True),
        sa.Column("destination_slot", sa.SmallInteger(), nullable=True),
        sa.Column("view_page", sa.SmallInteger(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_body", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "operation_id",
            name="pk_regional_storage_operations",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "area_id"],
            [
                "regional_storage_containers.life_id",
                "regional_storage_containers.area_id",
            ],
            name="fk_regional_storage_operations_container",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["item_instance_id", "life_id"],
            ["item_instances.item_instance_id", "item_instances.life_id"],
            name="fk_regional_storage_operations_item_life",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "move_kind IN ('deposit', 'withdraw', 'move')",
            name=op.f("ck_regional_storage_operations_kind"),
        ),
        sa.CheckConstraint(
            "expected_revision >= 0 AND resulting_revision = expected_revision + 1",
            name=op.f("ck_regional_storage_operations_revisions"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_regional_storage_operations_fingerprint"),
        ),
        sa.CheckConstraint(
            "view_page > 0",
            name=op.f("ck_regional_storage_operations_view_page"),
        ),
        sa.CheckConstraint(
            "(move_kind = 'deposit' "
            "AND source_page IS NULL AND source_slot IS NULL "
            "AND destination_page IS NOT NULL AND destination_slot IS NOT NULL) OR "
            "(move_kind = 'withdraw' "
            "AND source_page IS NOT NULL AND source_slot IS NOT NULL "
            "AND destination_page IS NULL AND destination_slot IS NULL) OR "
            "(move_kind = 'move' "
            "AND source_page IS NOT NULL AND source_slot IS NOT NULL "
            "AND destination_page IS NOT NULL AND destination_slot IS NOT NULL "
            "AND (source_page, source_slot) <> (destination_page, destination_slot))",
            name=op.f("ck_regional_storage_operations_shape"),
        ),
    )
    op.create_index(
        "ix_regional_storage_operations_life_created",
        "regional_storage_operations",
        ["life_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_regional_storage_operations_life_created",
        table_name="regional_storage_operations",
    )
    op.drop_table("regional_storage_operations")
    op.drop_index(
        "ix_regional_storage_slots_item_instance",
        table_name="regional_storage_slots",
    )
    op.drop_table("regional_storage_slots")
    op.drop_table("regional_storage_containers")
    op.drop_constraint(
        "uq_item_instances_identity_life",
        "item_instances",
        type_="unique",
    )
