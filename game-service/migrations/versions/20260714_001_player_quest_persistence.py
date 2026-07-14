"""Add player and quest persistence schema.

Revision ID: 20260714_001
Revises:
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("minecraft_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("last_known_name", sa.String(length=16), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
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
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("account_id", name="pk_accounts"),
        sa.UniqueConstraint("minecraft_uuid", name="uq_accounts_minecraft_uuid"),
        sa.CheckConstraint(
            "last_known_name ~ '^[A-Za-z0-9_]{3,16}$'",
            name=op.f("ck_accounts_last_known_name_format"),
        ),
        sa.CheckConstraint("revision > 0", name=op.f("ck_accounts_revision_positive")),
    )
    op.create_table(
        "account_minecraft_names",
        sa.Column("name_observation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_name", sa.String(length=16), nullable=False),
        sa.Column("normalized_name", sa.String(length=16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("name_observation_id", name="pk_account_minecraft_names"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_account_minecraft_names_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "account_id",
            "normalized_name",
            name="uq_account_minecraft_name",
        ),
        sa.CheckConstraint(
            "last_seen_at >= first_seen_at",
            name=op.f("ck_account_name_seen_order"),
        ),
        sa.CheckConstraint(
            "player_name ~ '^[A-Za-z0-9_]{3,16}$'",
            name=op.f("ck_account_name_format"),
        ),
        sa.CheckConstraint(
            "normalized_name = lower(player_name)",
            name=op.f("ck_account_name_normalized"),
        ),
    )
    op.create_index(
        "ix_account_names_normalized",
        "account_minecraft_names",
        ["normalized_name", sa.text("last_seen_at DESC")],
    )
    op.create_table(
        "lives",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "born_at",
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
        sa.Column("died_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("death_cause_code", sa.String(length=64), nullable=True),
        sa.Column("death_zone_id", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("life_id", name="pk_lives"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_lives_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("account_id", "generation_no", name="uq_life_generation"),
        sa.UniqueConstraint("life_id", "account_id", name="uq_life_account"),
        sa.CheckConstraint(
            "generation_no > 0",
            name=op.f("ck_lives_generation_positive"),
        ),
        sa.CheckConstraint("revision > 0", name=op.f("ck_lives_revision_positive")),
        sa.CheckConstraint(
            "status IN ('alive', 'reincarnated')",
            name=op.f("ck_life_status"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_life_terminal_fields"),
        ),
        sa.CheckConstraint(
            "died_at IS NULL OR died_at >= born_at",
            name=op.f("ck_life_time_order"),
        ),
    )
    op.create_index(
        "ux_lives_one_alive_per_account",
        "lives",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'alive'"),
    )
    op.execute(
        """
        CREATE FUNCTION prevent_life_delete_or_terminal_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'life rows are not deleted';
            END IF;
            IF OLD.status = 'reincarnated' AND NEW IS DISTINCT FROM OLD THEN
                RAISE EXCEPTION 'reincarnated life is immutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_lives_prevent_delete_terminal_mutation
        BEFORE UPDATE OR DELETE ON lives
        FOR EACH ROW EXECUTE FUNCTION prevent_life_delete_or_terminal_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION is_valid_spirit_root(
            root_quality VARCHAR,
            root_elements TEXT[],
            root_variant VARCHAR
        )
        RETURNS BOOLEAN
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
            SELECT
                array_ndims(root_elements) = 1
                AND array_position(root_elements, NULL) IS NULL
                AND root_elements = ARRAY(
                    SELECT element_code
                    FROM unnest(ARRAY['metal','wood','water','fire','earth']::TEXT[])
                         AS elements(element_code)
                    WHERE element_code = ANY(root_elements)
                )
                AND (
                    (root_quality = 'penta'
                        AND cardinality(root_elements) = 5
                        AND root_variant IS NULL)
                    OR
                    (root_quality = 'quad'
                        AND cardinality(root_elements) = 4
                        AND root_variant IS NULL)
                    OR
                    (root_quality = 'triple'
                        AND cardinality(root_elements) = 3
                        AND root_variant IS NULL)
                    OR
                    (root_quality = 'dual'
                        AND cardinality(root_elements) = 2
                        AND root_variant IS NULL)
                    OR
                    (root_quality = 'celestial'
                        AND cardinality(root_elements) = 1
                        AND root_variant IS NULL)
                    OR
                    (root_quality = 'variant'
                        AND cardinality(root_elements) = 1
                        AND (
                            (root_elements = ARRAY['fire']::TEXT[]
                                AND root_variant IN ('wind', 'thunder'))
                            OR (root_elements = ARRAY['wood']::TEXT[]
                                AND root_variant IN ('wind', 'ice'))
                            OR (root_elements = ARRAY['metal']::TEXT[]
                                AND root_variant IN ('thunder', 'dark'))
                            OR (root_elements = ARRAY['water']::TEXT[]
                                AND root_variant IN ('thunder', 'ice'))
                            OR (root_elements = ARRAY['earth']::TEXT[]
                                AND root_variant = 'dark')
                        ))
                );
        $$
        """
    )
    op.create_table(
        "life_spirit_roots",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_code", sa.String(length=20), nullable=False),
        sa.Column("base_element_codes", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("variant_element_code", sa.String(length=20), nullable=True),
        sa.Column("generator_version", sa.Integer(), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("life_id", name="pk_life_spirit_roots"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_spirit_roots_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "generator_version > 0",
            name=op.f("ck_life_spirit_roots_generator_version_positive"),
        ),
        sa.CheckConstraint(
            "quality_code IN ('quad', 'penta', 'triple', 'dual', 'variant', 'celestial')",
            name=op.f("ck_spirit_root_quality"),
        ),
        sa.CheckConstraint(
            """
            is_valid_spirit_root(
                quality_code,
                base_element_codes,
                variant_element_code
            ) IS TRUE
            """,
            name=op.f("ck_spirit_root_shape"),
        ),
    )
    op.execute(
        """
        CREATE FUNCTION prevent_spirit_root_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'spirit root is immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_spirit_roots_prevent_update_delete
        BEFORE UPDATE OR DELETE ON life_spirit_roots
        FOR EACH ROW EXECUTE FUNCTION prevent_spirit_root_mutation()
        """
    )
    op.create_table(
        "life_quest_states",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("life_id", name="pk_life_quest_states"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_life_quest_states_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "revision >= 0",
            name=op.f("ck_life_quest_states_revision_nonnegative"),
        ),
    )
    op.create_table(
        "quest_progress",
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("life_id", "quest_id", name="pk_quest_progress"),
        sa.ForeignKeyConstraint(
            ["life_id"],
            ["lives.life_id"],
            name="fk_quest_progress_life_id_lives",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "definition_version > 0",
            name=op.f("ck_quest_progress_definition_version_positive"),
        ),
        sa.CheckConstraint(
            "revision > 0",
            name=op.f("ck_quest_progress_revision_positive"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed')",
            name=op.f("ck_quest_progress_status"),
        ),
        sa.CheckConstraint(
            """
            (status = 'active' AND completed_at IS NULL)
            OR
            (status = 'completed' AND completed_at IS NOT NULL)
            """,
            name=op.f("ck_quest_progress_completion"),
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= accepted_at",
            name=op.f("ck_quest_progress_time_order"),
        ),
    )
    op.create_index(
        "ix_quest_progress_active_life",
        "quest_progress",
        ["life_id"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_quest_progress_revision",
        "quest_progress",
        ["life_id", "revision"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_quest_progress_reversal_or_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'quest progress rows are not deleted';
            END IF;
            IF OLD.life_id IS DISTINCT FROM NEW.life_id
               OR OLD.quest_id IS DISTINCT FROM NEW.quest_id
               OR OLD.definition_version IS DISTINCT FROM NEW.definition_version
               OR OLD.accepted_at IS DISTINCT FROM NEW.accepted_at THEN
                RAISE EXCEPTION 'quest progress identity and acceptance facts are immutable';
            END IF;
            IF NOT (OLD.status = 'active' AND NEW.status = 'completed') THEN
                RAISE EXCEPTION 'quest progress only transitions active to completed';
            END IF;
            IF NEW.revision <= OLD.revision THEN
                RAISE EXCEPTION 'quest progress revision must advance';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_quest_progress_prevent_reversal_delete
        BEFORE UPDATE OR DELETE ON quest_progress
        FOR EACH ROW EXECUTE FUNCTION prevent_quest_progress_reversal_or_delete()
        """
    )
    op.create_table(
        "quest_operations",
        sa.Column("operation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("life_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command", sa.String(length=20), nullable=False),
        sa.Column("quest_id", sa.String(length=128), nullable=False),
        sa.Column("provider_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("changed", sa.Boolean(), nullable=True),
        sa.Column("response_status", sa.SmallInteger(), nullable=True),
        sa.Column("response_content_type", sa.String(length=64), nullable=True),
        sa.Column("response_body", postgresql.BYTEA(), nullable=True),
        sa.Column("response_contract_version", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("operation_id", name="pk_quest_operations"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.account_id"],
            name="fk_quest_operations_account_id_accounts",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["life_id", "account_id"],
            ["lives.life_id", "lives.account_id"],
            name="fk_quest_operation_life_account",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "command IN ('accept', 'turn_in')",
            name=op.f("ck_quest_operation_command"),
        ),
        sa.CheckConstraint(
            "request_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_quest_operation_fingerprint"),
        ),
        sa.CheckConstraint(
            "state IN ('processing', 'succeeded', 'domain_failed')",
            name=op.f("ck_quest_operation_state"),
        ),
        sa.CheckConstraint(
            "response_content_type IS NULL OR response_content_type = 'application/json'",
            name=op.f("ck_quest_operation_content_type"),
        ),
        sa.CheckConstraint(
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
            name=op.f("ck_quest_operation_finalization"),
        ),
    )
    op.create_index(
        "ix_quest_operations_account_created",
        "quest_operations",
        ["account_id", sa.text("created_at DESC")],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_quest_operation_rewrite_or_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'quest operation rows are not deleted';
            END IF;
            IF OLD.state <> 'processing' THEN
                RAISE EXCEPTION 'finalized quest operations are immutable';
            END IF;
            IF OLD.operation_id IS DISTINCT FROM NEW.operation_id
               OR OLD.account_id IS DISTINCT FROM NEW.account_id
               OR OLD.life_id IS DISTINCT FROM NEW.life_id
               OR OLD.command IS DISTINCT FROM NEW.command
               OR OLD.quest_id IS DISTINCT FROM NEW.quest_id
               OR OLD.provider_id IS DISTINCT FROM NEW.provider_id
               OR OLD.request_fingerprint IS DISTINCT FROM NEW.request_fingerprint
               OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
                RAISE EXCEPTION 'quest operation request identity is immutable';
            END IF;
            IF NEW.state NOT IN ('succeeded', 'domain_failed') THEN
                RAISE EXCEPTION 'quest operation must finalize in one update';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_quest_operations_prevent_rewrite_delete
        BEFORE UPDATE OR DELETE ON quest_operations
        FOR EACH ROW EXECUTE FUNCTION prevent_quest_operation_rewrite_or_delete()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_quest_operations_prevent_rewrite_delete ON quest_operations"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS "
        "trg_quest_progress_prevent_reversal_delete ON quest_progress"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_spirit_roots_prevent_update_delete ON life_spirit_roots")
    op.execute("DROP TRIGGER IF EXISTS trg_lives_prevent_delete_terminal_mutation ON lives")

    op.drop_index("ix_quest_operations_account_created", table_name="quest_operations")
    op.drop_index("ix_quest_progress_revision", table_name="quest_progress")
    op.drop_index("ix_quest_progress_active_life", table_name="quest_progress")
    op.drop_index("ux_lives_one_alive_per_account", table_name="lives")
    op.drop_index("ix_account_names_normalized", table_name="account_minecraft_names")

    op.drop_table("quest_operations")
    op.drop_table("quest_progress")
    op.drop_table("life_quest_states")
    op.drop_table("life_spirit_roots")
    op.drop_table("lives")
    op.drop_table("account_minecraft_names")
    op.drop_table("accounts")

    op.execute("DROP FUNCTION IF EXISTS prevent_quest_operation_rewrite_or_delete()")
    op.execute("DROP FUNCTION IF EXISTS prevent_quest_progress_reversal_or_delete()")
    op.execute("DROP FUNCTION IF EXISTS prevent_spirit_root_mutation()")
    op.execute("DROP FUNCTION IF EXISTS is_valid_spirit_root(VARCHAR, TEXT[], VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS prevent_life_delete_or_terminal_mutation()")
