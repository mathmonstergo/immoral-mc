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
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class LifeCultivationStateRow(Base):
    __tablename__ = "life_cultivation_states"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", name=conv("pk_life_cultivation_states")),
        ForeignKeyConstraint(
            ["life_id", "active_session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_cultivation_state_active_session"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "current_level BETWEEN 1 AND 22",
            name=conv("ck_life_cultivation_states_level"),
        ),
        CheckConstraint(
            "unrefined_cultivation >= 0",
            name=conv("ck_life_cultivation_states_unrefined_nonnegative"),
        ),
        CheckConstraint(
            "realized_cultivation >= 0",
            name=conv("ck_life_cultivation_states_realized_nonnegative"),
        ),
        CheckConstraint(
            "revision > 0",
            name=conv("ck_life_cultivation_states_revision_positive"),
        ),
    )
    current_level: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("1"),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_life_cultivation_states_life_id_lives"),
            ondelete="RESTRICT",
        ),
    )
    unrefined_cultivation: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
    realized_cultivation: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("0"),
    )
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("1"),
    )
    active_session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class CultivationResourceEntryRow(Base):
    __tablename__ = "cultivation_resource_entries"
    __table_args__ = (
        PrimaryKeyConstraint(
            "entry_id",
            name=conv("pk_cultivation_resource_entries"),
        ),
        CheckConstraint(
            "resource_code IN ('unrefined_cultivation', 'realized_cultivation')",
            name=conv("ck_cultivation_resource_code"),
        ),
        CheckConstraint(
            """
            entry_type IN (
                'combat_reward', 'seclusion_consumption',
                'seclusion_realization', 'technique_abandonment',
                'technique_transfer', 'breakthrough_penalty',
                'administrative_adjustment'
            )
            """,
            name=conv("ck_cultivation_entry_type"),
        ),
        CheckConstraint(
            "delta_amount <> 0",
            name=conv("ck_cultivation_entry_delta"),
        ),
        CheckConstraint(
            "balance_after >= 0",
            name=conv("ck_cultivation_entry_balance_nonnegative"),
        ),
        CheckConstraint(
            """
            (entry_type = 'combat_reward'
                AND resource_code = 'unrefined_cultivation'
                AND delta_amount > 0
                AND kill_event_id IS NOT NULL)
            OR
            (entry_type <> 'combat_reward' AND kill_event_id IS NULL)
            """,
            name=conv("ck_cultivation_combat_source"),
        ),
        UniqueConstraint(
            "operation_id",
            "life_id",
            "resource_code",
            name=conv("uq_cultivation_operation_resource"),
        ),
        ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_cultivation_entries_session"),
            ondelete="RESTRICT",
        ),
        Index(
            "ux_cultivation_kill_recipient",
            "kill_event_id",
            "life_id",
            "resource_code",
            unique=True,
            postgresql_where=text("entry_type = 'combat_reward'"),
        ),
    )

    entry_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_cultivation_resource_entries_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    resource_code: Mapped[str] = mapped_column(String(32), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kill_event_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "combat_kill_events.kill_event_id",
            name=conv("fk_cultivation_entries_kill_event"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    operation_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class LifeTechniqueRow(Base):
    __tablename__ = "life_techniques"
    __table_args__ = (
        PrimaryKeyConstraint("life_technique_id", name=conv("pk_life_techniques")),
        UniqueConstraint("life_id", "technique_id", name=conv("uq_life_technique_catalog")),
        UniqueConstraint(
            "life_id",
            "life_technique_id",
            name=conv("uq_life_technique_identity"),
        ),
        CheckConstraint(
            "definition_version > 0",
            name=conv("ck_life_technique_definition_version"),
        ),
        CheckConstraint(
            "group_code = 'qi' OR group_code ~ '^level:(1[4-9]|2[0-2])$'",
            name=conv("ck_life_technique_group"),
        ),
        CheckConstraint(
            "major_realm IN ('练气', '筑基', '结丹', '元婴')",
            name=conv("ck_life_technique_major_realm"),
        ),
        CheckConstraint(
            "max_investment > 0 AND invested_amount BETWEEN 0 AND max_investment",
            name=conv("ck_life_technique_investment"),
        ),
        CheckConstraint(
            "current_layer BETWEEN 0 AND 13",
            name=conv("ck_life_technique_layer"),
        ),
        CheckConstraint(
            "status IN ('active', 'abandoned')",
            name=conv("ck_life_technique_status"),
        ),
        Index(
            "ix_life_techniques_group_status",
            "life_id",
            "group_code",
            "status",
        ),
    )

    life_technique_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_life_techniques_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    technique_id: Mapped[str] = mapped_column(String(128), nullable=False)
    definition_version: Mapped[int] = mapped_column(nullable=False)
    group_code: Mapped[str] = mapped_column(String(32), nullable=False)
    major_realm: Mapped[str] = mapped_column(String(32), nullable=False)
    invested_amount: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    max_investment: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_layer: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'active'"))
    learned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CultivationSessionRow(Base):
    __tablename__ = "cultivation_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("session_id", name=conv("pk_cultivation_sessions")),
        UniqueConstraint("life_id", "session_id", name=conv("uq_cultivation_session_identity")),
        UniqueConstraint(
            "life_id",
            "idempotency_key",
            name=conv("uq_cultivation_session_idempotency"),
        ),
        CheckConstraint(
            "session_kind IN ('ordinary', 'breakthrough', 'technique_mutation')",
            name=conv("ck_cultivation_session_kind"),
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'completed', 'failed', 'cancelled')",
            name=conv("ck_cultivation_session_status"),
        ),
        CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=conv("ck_cultivation_session_fingerprint"),
        ),
        CheckConstraint(
            "source_level BETWEEN 1 AND 22 AND "
            "(target_level IS NULL OR target_level BETWEEN 1 AND 22)",
            name=conv("ck_cultivation_session_levels"),
        ),
        CheckConstraint(
            "cumulative_elapsed_seconds >= 0 AND cumulative_generated >= 0 "
            "AND cumulative_reserve_consumed >= 0 AND cumulative_retained >= 0",
            name=conv("ck_cultivation_session_totals"),
        ),
        CheckConstraint(
            "completes_at >= started_at AND (settled_at IS NULL OR settled_at >= started_at)",
            name=conv("ck_cultivation_session_times"),
        ),
        CheckConstraint(
            "(session_kind = 'ordinary' AND area_id IS NOT NULL "
            "AND target_level IS NULL) OR "
            "(session_kind = 'breakthrough' AND area_id IS NULL "
            "AND target_level IS NOT NULL) OR "
            "(session_kind = 'technique_mutation' AND area_id IS NULL "
            "AND target_level IS NULL AND status = 'completed')",
            name=conv("ck_cultivation_session_shape"),
        ),
        CheckConstraint("revision > 0", name=conv("ck_cultivation_session_revision")),
        Index(
            "ux_cultivation_one_open_session",
            "life_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'active')"),
        ),
        Index(
            "ix_cultivation_sessions_life_created",
            "life_id",
            text("created_at DESC"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_cultivation_sessions_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    session_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    area_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    frozen_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB(none_as_null=True), nullable=False
    )
    cumulative_elapsed_seconds: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cumulative_generated: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cumulative_reserve_consumed: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    cumulative_retained: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class LifeRealmEntryRow(Base):
    __tablename__ = "life_realm_entries"
    __table_args__ = (
        PrimaryKeyConstraint("realm_entry_id", name=conv("pk_life_realm_entries")),
        ForeignKeyConstraint(
            ["life_id", "parent_entry_id"],
            ["life_realm_entries.life_id", "life_realm_entries.realm_entry_id"],
            name=conv("fk_life_realm_entries_parent"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "transition_session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_life_realm_entries_session"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint("life_id", "generation", name=conv("uq_life_realm_entry_generation")),
        UniqueConstraint(
            "life_id",
            "realm_entry_id",
            name=conv("uq_life_realm_entry_identity"),
        ),
        CheckConstraint("generation > 0", name=conv("ck_life_realm_entry_generation")),
        CheckConstraint(
            "source_level BETWEEN 1 AND 22 AND target_level BETWEEN 1 AND 22 "
            "AND target_level > source_level",
            name=conv("ck_life_realm_entry_levels"),
        ),
        CheckConstraint(
            "source_floor >= 0 AND target_baseline >= 0",
            name=conv("ck_life_realm_entry_amounts"),
        ),
        CheckConstraint(
            "transition_kind IN ('adjacent', 'breakthrough', 'failure_advance', 'reentry')",
            name=conv("ck_life_realm_entry_transition"),
        ),
        CheckConstraint(
            "status IN ('active', 'invalidated')",
            name=conv("ck_life_realm_entry_status"),
        ),
        CheckConstraint(
            "(status = 'active' AND invalidated_at IS NULL) OR "
            "(status = 'invalidated' AND invalidated_at IS NOT NULL)",
            name=conv("ck_life_realm_entry_invalidation"),
        ),
        Index(
            "ix_life_realm_entries_active_chain",
            "life_id",
            "generation",
            postgresql_where=text("status = 'active'"),
        ),
    )

    realm_entry_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_life_realm_entries_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    generation: Mapped[int] = mapped_column(nullable=False)
    parent_entry_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=True
    )
    source_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source_group: Mapped[str] = mapped_column(String(32), nullable=False)
    target_group: Mapped[str] = mapped_column(String(32), nullable=False)
    source_floor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_baseline: Mapped[int] = mapped_column(BigInteger, nullable=False)
    transition_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    transition_session_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class CultivationSessionTechniqueRow(Base):
    __tablename__ = "cultivation_session_techniques"
    __table_args__ = (
        PrimaryKeyConstraint(
            "session_id",
            "life_technique_id",
            name=conv("pk_cultivation_session_techniques"),
        ),
        ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_session_techniques_session"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name=conv("fk_session_techniques_technique"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "definition_version > 0",
            name=conv("ck_session_technique_definition_version"),
        ),
        CheckConstraint(
            "frozen_capacity > 0 AND frozen_invested BETWEEN 0 AND frozen_capacity",
            name=conv("ck_session_technique_frozen_amounts"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    life_technique_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    definition_version: Mapped[int] = mapped_column(nullable=False)
    group_code: Mapped[str] = mapped_column(String(32), nullable=False)
    major_realm: Mapped[str] = mapped_column(String(32), nullable=False)
    frozen_capacity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    frozen_invested: Mapped[int] = mapped_column(BigInteger, nullable=False)


class TechniqueInvestmentEntryRow(Base):
    __tablename__ = "technique_investment_entries"
    __table_args__ = (
        PrimaryKeyConstraint("entry_id", name=conv("pk_technique_investment_entries")),
        ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name=conv("fk_technique_investment_technique"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_technique_investment_session"),
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "operation_id",
            "life_technique_id",
            name=conv("uq_technique_investment_operation"),
        ),
        CheckConstraint(
            "entry_type IN ('seclusion_realization', 'abandonment', "
            "'transfer_in', 'transfer_out', 'breakthrough_penalty', "
            "'administrative_adjustment')",
            name=conv("ck_technique_investment_entry_type"),
        ),
        CheckConstraint("delta_amount <> 0", name=conv("ck_technique_investment_delta")),
        CheckConstraint("balance_after >= 0", name=conv("ck_technique_investment_balance")),
        Index(
            "ix_technique_investment_life_created",
            "life_id",
            text("created_at DESC"),
        ),
    )

    entry_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    life_technique_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    operation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class BreakthroughTechniqueDebitRow(Base):
    __tablename__ = "breakthrough_technique_debits"
    __table_args__ = (
        PrimaryKeyConstraint(
            "session_id",
            "life_technique_id",
            name=conv("pk_breakthrough_technique_debits"),
        ),
        ForeignKeyConstraint(
            ["life_id", "session_id"],
            ["cultivation_sessions.life_id", "cultivation_sessions.session_id"],
            name=conv("fk_breakthrough_debits_session"),
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["life_id", "life_technique_id"],
            ["life_techniques.life_id", "life_techniques.life_technique_id"],
            name=conv("fk_breakthrough_debits_technique"),
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "allocated_amount >= 0 AND balance_before >= allocated_amount "
            "AND balance_after = balance_before - allocated_amount",
            name=conv("ck_breakthrough_debit_amounts"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    life_technique_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    allocated_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
