from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class CombatKillEventRow(Base):
    __tablename__ = "combat_kill_events"
    __table_args__ = (
        PrimaryKeyConstraint("kill_event_id", name=conv("pk_combat_kill_events")),
        UniqueConstraint(
            "source_type",
            "source_event_id",
            name=conv("uq_combat_kill_source"),
        ),
        CheckConstraint(
            "source_type = 'mythicmob_death'",
            name=conv("ck_combat_kill_source_type"),
        ),
        CheckConstraint("mob_level >= 0", name=conv("ck_combat_kill_level")),
        CheckConstraint(
            """
            attribution_kind IN (
                'direct', 'projectile', 'damage_over_time', 'summon',
                'trap', 'formation', 'bukkit_fallback'
            )
            """,
            name=conv("ck_combat_kill_attribution"),
        ),
        CheckConstraint(
            """
            outcome IN (
                'rewarded', 'not_rewardable', 'account_not_found',
                'current_life_unavailable'
            )
            """,
            name=conv("ck_combat_kill_outcome"),
        ),
        CheckConstraint(
            "telemetry IN ('compact', 'detailed')",
            name=conv("ck_combat_kill_telemetry"),
        ),
        CheckConstraint(
            """
            (telemetry = 'compact' AND detail_payload IS NULL)
            OR telemetry = 'detailed'
            """,
            name=conv("ck_combat_kill_detail"),
        ),
        CheckConstraint(
            """
            (outcome = 'rewarded'
                AND account_id IS NOT NULL
                AND life_id IS NOT NULL
                AND reward_amount IS NOT NULL
                AND reward_amount > 0)
            OR
            (outcome <> 'rewarded' AND reward_amount IS NULL)
            """,
            name=conv("ck_combat_kill_reward_shape"),
        ),
        Index(
            "ix_combat_kills_life_time",
            "life_id",
            text("occurred_at DESC"),
            postgresql_where=text("life_id IS NOT NULL"),
        ),
        Index(
            "ix_combat_kills_mob_time",
            "mob_internal_name",
            text("occurred_at DESC"),
        ),
    )

    kill_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    server_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_uuid: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    mob_internal_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mob_level: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    killer_minecraft_uuid: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    source_life_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_combat_kill_events_source_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    attribution_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    technique_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cast_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    account_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "accounts.account_id",
            name=conv("fk_combat_kill_events_account_id_accounts"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    life_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_combat_kill_events_life_id_lives"),
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    world_key: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    telemetry: Mapped[str] = mapped_column(String(16), nullable=False)
    detail_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )
    reward_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class LifeMobKillCounterRow(Base):
    __tablename__ = "life_mob_kill_counters"
    __table_args__ = (
        PrimaryKeyConstraint(
            "life_id",
            "mob_internal_name",
            name=conv("pk_life_mob_kill_counters"),
        ),
        CheckConstraint(
            "kill_count > 0",
            name=conv("ck_life_mob_kill_counters_count_positive"),
        ),
        CheckConstraint(
            "last_killed_at >= first_killed_at",
            name=conv("ck_life_mob_kill_time"),
        ),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            name=conv("fk_life_mob_kill_counters_life_id_lives"),
            ondelete="RESTRICT",
        ),
    )
    mob_internal_name: Mapped[str] = mapped_column(String(128))
    kill_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    first_killed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_killed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
