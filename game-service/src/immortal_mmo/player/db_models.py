from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import conv

from immortal_mmo.db.base import Base


class AccountRow(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        PrimaryKeyConstraint("account_id", name=conv("pk_accounts")),
        UniqueConstraint("minecraft_uuid", name=conv("uq_accounts_minecraft_uuid")),
        CheckConstraint(
            "last_known_name ~ '^[A-Za-z0-9_]{3,16}$'",
            name=conv("ck_accounts_last_known_name_format"),
        ),
        CheckConstraint("revision > 0", name=conv("ck_accounts_revision_positive")),
    )

    account_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    minecraft_uuid: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    last_known_name: Mapped[str] = mapped_column(String(16), nullable=False)
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
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class AccountMinecraftNameRow(Base):
    __tablename__ = "account_minecraft_names"
    __table_args__ = (
        PrimaryKeyConstraint(
            "name_observation_id",
            name=conv("pk_account_minecraft_names"),
        ),
        UniqueConstraint(
            "account_id",
            "normalized_name",
            name=conv("uq_account_minecraft_name"),
        ),
        CheckConstraint(
            "last_seen_at >= first_seen_at",
            name=conv("ck_account_name_seen_order"),
        ),
        CheckConstraint(
            "player_name ~ '^[A-Za-z0-9_]{3,16}$'",
            name=conv("ck_account_name_format"),
        ),
        CheckConstraint(
            "normalized_name = lower(player_name)",
            name=conv("ck_account_name_normalized"),
        ),
        Index(
            "ix_account_names_normalized",
            "normalized_name",
            text("last_seen_at DESC"),
        ),
    )

    name_observation_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
            name=conv("fk_account_minecraft_names_account_id_accounts"),
        ),
        nullable=False,
    )
    player_name: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(16), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LifeRow(Base):
    __tablename__ = "lives"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", name=conv("pk_lives")),
        UniqueConstraint(
            "account_id",
            "generation_no",
            name=conv("uq_life_generation"),
        ),
        UniqueConstraint("life_id", "account_id", name=conv("uq_life_account")),
        CheckConstraint(
            "generation_no > 0",
            name=conv("ck_lives_generation_positive"),
        ),
        CheckConstraint("revision > 0", name=conv("ck_lives_revision_positive")),
        CheckConstraint(
            "status IN ('alive', 'reincarnated')",
            name=conv("ck_life_status"),
        ),
        CheckConstraint(
            """
            (status = 'alive'
                AND died_at IS NULL
                AND death_cause_code IS NULL
                AND death_zone_id IS NULL)
            OR
            (status = 'reincarnated'
                AND died_at IS NOT NULL
                AND death_cause_code IS NOT NULL)
            """,
            name=conv("ck_life_terminal_fields"),
        ),
        CheckConstraint(
            "died_at IS NULL OR died_at >= born_at",
            name=conv("ck_life_time_order"),
        ),
        Index(
            "ux_lives_one_alive_per_account",
            "account_id",
            unique=True,
            postgresql_where=text("status = 'alive'"),
        ),
    )

    life_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True))
    account_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "accounts.account_id",
            ondelete="RESTRICT",
            name=conv("fk_lives_account_id_accounts"),
        ),
        nullable=False,
    )
    generation_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=text("1"),
    )
    born_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    died_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    death_cause_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    death_zone_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class LifeSpiritRootRow(Base):
    __tablename__ = "life_spirit_roots"
    __table_args__ = (
        PrimaryKeyConstraint("life_id", name=conv("pk_life_spirit_roots")),
        CheckConstraint(
            "generator_version > 0",
            name=conv("ck_life_spirit_roots_generator_version_positive"),
        ),
        CheckConstraint(
            "quality_code IN ('quad', 'penta', 'triple', 'dual', 'variant', 'celestial')",
            name=conv("ck_spirit_root_quality"),
        ),
        CheckConstraint(
            """
            is_valid_spirit_root(
                quality_code,
                base_element_codes,
                variant_element_code
            ) IS TRUE
            """,
            name=conv("ck_spirit_root_shape"),
        ),
    )

    life_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "lives.life_id",
            ondelete="RESTRICT",
            name=conv("fk_life_spirit_roots_life_id_lives"),
        ),
    )
    quality_code: Mapped[str] = mapped_column(String(20), nullable=False)
    base_element_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    variant_element_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    generator_version: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
