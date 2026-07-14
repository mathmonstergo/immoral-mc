from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class LifeQuestStateRow(Base):
    __tablename__ = "life_quest_states"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", name=conv("pk_life_quest_states")),
        CheckConstraint(
            "revision >= 0",
            name=conv("ck_life_quest_states_revision_nonnegative"),
        ),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            ondelete="RESTRICT",
            name=conv("fk_life_quest_states_life_id_lives"),
        ),
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class QuestProgressRow(Base):
    __tablename__ = "quest_progress"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", "quest_id", name=conv("pk_quest_progress")),
        CheckConstraint(
            "definition_version > 0",
            name=conv("ck_quest_progress_definition_version_positive"),
        ),
        CheckConstraint(
            "revision > 0",
            name=conv("ck_quest_progress_revision_positive"),
        ),
        CheckConstraint(
            "status IN ('active', 'completed')",
            name=conv("ck_quest_progress_status"),
        ),
        CheckConstraint(
            """
            (status = 'active' AND completed_at IS NULL)
            OR
            (status = 'completed' AND completed_at IS NOT NULL)
            """,
            name=conv("ck_quest_progress_completion"),
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= accepted_at",
            name=conv("ck_quest_progress_time_order"),
        ),
        Index(
            "ix_quest_progress_active_life",
            "life_id",
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_quest_progress_revision", "life_id", "revision"),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            ondelete="RESTRICT",
            name=conv("fk_quest_progress_life_id_lives"),
        ),
    )
    quest_id: Mapped[str] = mapped_column(String(128))
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class QuestOperationRow(Base):
    __tablename__ = "quest_operations"
    __table_args__ = (
        PrimaryKeyConstraint("operation_id", name=conv("pk_quest_operations")),
        ForeignKeyConstraint(
            ["life_id", "account_id"],
            ["lives.life_id", "lives.account_id"],
            name=conv("fk_quest_operation_life_account"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "command IN ('accept', 'turn_in')",
            name=conv("ck_quest_operation_command"),
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_quest_operation_fingerprint"),
        ),
        CheckConstraint(
            "state IN ('processing', 'succeeded', 'domain_failed')",
            name=conv("ck_quest_operation_state"),
        ),
        CheckConstraint(
            "response_content_type IS NULL OR response_content_type = 'application/json'",
            name=conv("ck_quest_operation_content_type"),
        ),
        CheckConstraint(
            """
            ((state = 'processing'
                AND changed IS NULL
                AND response_status IS NULL
                AND response_content_type IS NULL
                AND response_body IS NULL
                AND response_contract_version IS NULL
                AND finalized_at IS NULL)
            OR
            (state = 'succeeded'
                AND changed IS NOT NULL
                AND response_status IS NOT NULL
                AND response_status BETWEEN 200 AND 299
                AND response_content_type IS NOT NULL
                AND response_body IS NOT NULL
                AND response_contract_version IS NOT NULL
                AND finalized_at IS NOT NULL)
            OR
            (state = 'domain_failed'
                AND changed IS FALSE
                AND response_status IS NOT NULL
                AND response_status BETWEEN 400 AND 499
                AND response_content_type IS NOT NULL
                AND response_body IS NOT NULL
                AND response_contract_version IS NOT NULL
                AND finalized_at IS NOT NULL)) IS TRUE
            """,
            name=conv("ck_quest_operation_finalization"),
        ),
        Index(
            "ix_quest_operations_account_created",
            "account_id",
            text("created_at DESC"),
        ),
    )

    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
            name=conv("fk_quest_operations_account_id_accounts"),
        ),
        nullable=False,
    )
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    command: Mapped[str] = mapped_column(String(20), nullable=False)
    quest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    response_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    response_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_body: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    response_contract_version: Mapped[int | None] = mapped_column(
        SmallInteger,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
