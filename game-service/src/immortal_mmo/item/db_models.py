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
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class LifeItemStackRow(Base):
    __tablename__ = "life_item_stacks"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", "item_code", name=conv("pk_life_item_stacks")),
        CheckConstraint("quantity >= 0", name=conv("ck_life_item_stack_quantity")),
        CheckConstraint("revision > 0", name=conv("ck_life_item_stack_revision")),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_life_item_stacks_life_id_lives"),
            ondelete="RESTRICT",
        ),
    )
    item_code: Mapped[str] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ItemInstanceRow(Base):
    """Authoritative identity for a physical Minecraft item projection."""

    __tablename__ = "item_instances"
    __table_args__ = (
        PrimaryKeyConstraint("item_instance_id", name=conv("pk_item_instances")),
        CheckConstraint(
            "definition_version > 0",
            name=conv("ck_item_instances_definition_version"),
        ),
        CheckConstraint(
            "issuance_ordinal >= 0",
            name=conv("ck_item_instances_issuance_ordinal"),
        ),
        CheckConstraint(
            "status IN ('pending_delivery', 'owned', 'consumed')",
            name=conv("ck_item_instances_status"),
        ),
        CheckConstraint(
            "(status = 'pending_delivery' AND location IS NULL "
            "AND delivered_at IS NULL AND consumed_at IS NULL) OR "
            "(status = 'owned' AND location IN ('inventory', 'storage') "
            "AND delivered_at IS NOT NULL AND consumed_at IS NULL) OR "
            "(status = 'consumed' AND location IS NULL AND consumed_at IS NOT NULL)",
            name=conv("ck_item_instances_state_shape"),
        ),
        Index("ix_item_instances_life_status", "life_id", "status"),
        UniqueConstraint(
            "issuance_id",
            "issuance_ordinal",
            name=conv("uq_item_instances_issuance"),
        ),
        UniqueConstraint(
            "item_instance_id",
            "life_id",
            name=conv("uq_item_instances_identity_life"),
        ),
    )

    item_instance_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_item_instances_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    issuance_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    issuance_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    quest_reward_grant_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "quest_reward_grants.grant_id",
            name=conv("fk_item_instances_quest_reward_grant"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    item_code: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    technique_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    location: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ItemResourceEntryRow(Base):
    __tablename__ = "item_resource_entries"
    __table_args__ = (
        PrimaryKeyConstraint("entry_id", name=conv("pk_item_resource_entries")),
        ForeignKeyConstraint(
            ["life_id", "item_code"],
            ["life_item_stacks.life_id", "life_item_stacks.item_code"],
            name=conv("fk_item_resource_entries_stack"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_item_resource_entries_session"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint("operation_id", "item_code", name=conv("uq_item_resource_operation")),
        CheckConstraint(
            "entry_type IN ('breakthrough_consumption', 'administrative_adjustment')",
            name=conv("ck_item_resource_entry_type"),
        ),
        CheckConstraint("delta_quantity <> 0", name=conv("ck_item_resource_delta")),
        CheckConstraint("balance_after >= 0", name=conv("ck_item_resource_balance")),
        CheckConstraint(
            "(entry_type = 'breakthrough_consumption' "
            "AND delta_quantity < 0 AND session_id IS NOT NULL) OR "
            "(entry_type = 'administrative_adjustment' AND session_id IS NULL)",
            name=conv("ck_item_resource_session_shape"),
        ),
        Index(
            "ix_item_resource_life_created",
            "life_id",
            text("created_at DESC"),
        ),
    )

    entry_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    item_code: Mapped[str] = mapped_column(String(128), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
