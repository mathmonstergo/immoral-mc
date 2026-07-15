from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class LifeCultivationStateRow(Base):
    __tablename__ = "life_cultivation_states"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", name=conv("pk_life_cultivation_states")),
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
                'seclusion_realization', 'administrative_adjustment'
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
