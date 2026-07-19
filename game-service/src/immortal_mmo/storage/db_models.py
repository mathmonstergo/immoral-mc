from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class RegionalStorageContainerRow(Base):
    __tablename__ = "regional_storage_containers"
    __table_args__ = (
        PrimaryKeyConstraint(
            "life_id",
            "area_id",
            name=conv("pk_regional_storage_containers"),
        ),
        CheckConstraint(
            "area_id ~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'",
            name=conv("ck_regional_storage_containers_area_id"),
        ),
        CheckConstraint(
            "page_count BETWEEN 1 AND 100",
            name=conv("ck_regional_storage_containers_page_count"),
        ),
        CheckConstraint(
            "item_slots_per_page BETWEEN 1 AND 45",
            name=conv("ck_regional_storage_containers_item_slots"),
        ),
        CheckConstraint(
            "revision >= 0",
            name=conv("ck_regional_storage_containers_revision"),
        ),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_regional_storage_containers_life_id_lives"),
            ondelete="RESTRICT",
        ),
    )
    area_id: Mapped[str] = mapped_column(String(128))
    page_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    item_slots_per_page: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RegionalStorageSlotRow(Base):
    __tablename__ = "regional_storage_slots"
    __table_args__ = (
        PrimaryKeyConstraint(
            "life_id",
            "area_id",
            "page",
            "slot",
            name=conv("pk_regional_storage_slots"),
        ),
        ForeignKeyConstraint(
            ["life_id", "area_id"],
            [
                "regional_storage_containers.life_id",
                "regional_storage_containers.area_id",
            ],
            name=conv("fk_regional_storage_slots_container"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["item_instance_id", "life_id"],
            ["item_instances.item_instance_id", "item_instances.life_id"],
            name=conv("fk_regional_storage_slots_item_life"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "item_instance_id",
            name=conv("uq_regional_storage_slots_item_instance"),
        ),
        CheckConstraint(
            "page > 0",
            name=conv("ck_regional_storage_slots_page"),
        ),
        CheckConstraint(
            "slot BETWEEN 0 AND 44",
            name=conv("ck_regional_storage_slots_slot"),
        ),
        Index(
            "ix_regional_storage_slots_item_instance",
            "item_instance_id",
        ),
    )

    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    area_id: Mapped[str] = mapped_column(String(128))
    page: Mapped[int] = mapped_column(SmallInteger)
    slot: Mapped[int] = mapped_column(SmallInteger)
    item_instance_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RegionalStorageOperationRow(Base):
    __tablename__ = "regional_storage_operations"
    __table_args__ = (
        PrimaryKeyConstraint(
            "operation_id",
            name=conv("pk_regional_storage_operations"),
        ),
        ForeignKeyConstraint(
            ["life_id", "area_id"],
            [
                "regional_storage_containers.life_id",
                "regional_storage_containers.area_id",
            ],
            name=conv("fk_regional_storage_operations_container"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["item_instance_id", "life_id"],
            ["item_instances.item_instance_id", "item_instances.life_id"],
            name=conv("fk_regional_storage_operations_item_life"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "move_kind IN ('deposit', 'withdraw', 'move')",
            name=conv("ck_regional_storage_operations_kind"),
        ),
        CheckConstraint(
            "expected_revision >= 0 AND resulting_revision = expected_revision + 1",
            name=conv("ck_regional_storage_operations_revisions"),
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_regional_storage_operations_fingerprint"),
        ),
        CheckConstraint(
            "view_page > 0",
            name=conv("ck_regional_storage_operations_view_page"),
        ),
        CheckConstraint(
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
            name=conv("ck_regional_storage_operations_shape"),
        ),
        Index(
            "ix_regional_storage_operations_life_created",
            "life_id",
            text("created_at DESC"),
        ),
    )

    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    area_id: Mapped[str] = mapped_column(String(128), nullable=False)
    move_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    item_instance_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )
    expected_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    resulting_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_page: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    destination_page: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    destination_slot: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    view_page: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_body: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
