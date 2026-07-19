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
    UniqueConstraint,
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


class QuestObjectiveProgressRow(Base):
    __tablename__ = "quest_objective_progress"
    __table_args__ = (
        PrimaryKeyConstraint(
            "life_id",
            "quest_id",
            "objective_id",
            name=conv("pk_quest_objective_progress"),
        ),
        ForeignKeyConstraint(
            ["life_id", "quest_id"],
            ["quest_progress.life_id", "quest_progress.quest_id"],
            name=conv("fk_quest_objective_progress_quest"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "definition_version > 0",
            name=conv("ck_quest_objective_progress_definition_version_positive"),
        ),
        CheckConstraint(
            "objective_type = 'mythicmob_kill_count'",
            name=conv("ck_quest_objective_progress_type"),
        ),
        CheckConstraint(
            "required_value > 0",
            name=conv("ck_quest_objective_progress_required_positive"),
        ),
        CheckConstraint(
            "current_value >= 0 AND current_value <= required_value",
            name=conv("ck_quest_objective_progress_current_bounds"),
        ),
        Index(
            "ix_quest_objective_progress_target",
            "life_id",
            "objective_type",
            "target_id",
        ),
    )

    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    quest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    objective_id: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    objective_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    required_value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
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


class QuestRewardGrantRow(Base):
    __tablename__ = "quest_reward_grants"
    __table_args__ = (
        PrimaryKeyConstraint("grant_id", name=conv("pk_quest_reward_grants")),
        ForeignKeyConstraint(
            ["operation_id"],
            ["quest_operations.operation_id"],
            name=conv("fk_quest_reward_grants_operation"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "quest_id"],
            ["quest_progress.life_id", "quest_progress.quest_id"],
            name=conv("fk_quest_reward_grants_progress"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "operation_id",
            "reward_id",
            name=conv("uq_quest_reward_grants_operation_reward"),
        ),
        CheckConstraint(
            "reward_type IN ('fixed_item', 'unrefined_cultivation')",
            name=conv("ck_quest_reward_grants_type"),
        ),
        CheckConstraint(
            "configured_amount > 0 AND applied_amount >= 0 AND pending_amount >= 0 "
            "AND applied_amount + pending_amount = configured_amount",
            name=conv("ck_quest_reward_grants_amounts"),
        ),
        CheckConstraint(
            "status IN ('applied', 'pending')",
            name=conv("ck_quest_reward_grants_status"),
        ),
        CheckConstraint(
            "(reward_type = 'fixed_item' AND item_code IS NOT NULL) OR "
            "(reward_type = 'unrefined_cultivation' AND item_code IS NULL)",
            name=conv("ck_quest_reward_grants_item_shape"),
        ),
        CheckConstraint(
            "(status = 'applied' AND pending_amount = 0) OR "
            "(status = 'pending' AND pending_amount > 0)",
            name=conv("ck_quest_reward_grants_status_shape"),
        ),
        Index("ix_quest_reward_grants_life_status", "life_id", "status"),
    )

    grant_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    quest_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reward_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reward_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    configured_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    applied_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pending_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
