"""add audit logs

Revision ID: 5b746a74fefd
Revises: 1881a4d6b546
Create Date: 2026-10-27 03:24:56.832119

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b746a74fefd"
down_revision: Union[str, Sequence[str], None] = "1881a4d6b546"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create audit_logs table."""

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("university_id", sa.Integer(), nullable=True),
        sa.Column("transport_company_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("old_values", sa.JSON(), nullable=True),
        sa.Column("new_values", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_audit_logs_description_not_empty",
        ),
        sa.CheckConstraint(
            "entity_id IS NULL OR entity_id > 0",
            name="ck_audit_logs_entity_id_positive",
        ),
        sa.CheckConstraint(
            "ip_address IS NULL OR length(trim(ip_address)) > 0",
            name="ck_audit_logs_ip_address_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(action)) > 0",
            name="ck_audit_logs_action_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(entity_type)) > 0",
            name="ck_audit_logs_entity_type_not_empty",
        ),
        sa.CheckConstraint(
            "transport_company_id IS NULL OR transport_company_id > 0",
            name="ck_audit_logs_company_id_positive",
        ),
        sa.CheckConstraint(
            "university_id IS NULL OR university_id > 0",
            name="ck_audit_logs_university_id_positive",
        ),
        sa.CheckConstraint(
            "user_agent IS NULL OR length(trim(user_agent)) > 0",
            name="ck_audit_logs_user_agent_not_empty",
        ),
        sa.CheckConstraint(
            "user_id IS NULL OR user_id > 0",
            name="ck_audit_logs_user_id_positive",
        ),

        sa.ForeignKeyConstraint(
            ["transport_company_id"],
            ["transport_companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["university_id"],
            ["universities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_action_created_at",
        "audit_logs",
        ["action", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_company_created_at",
        "audit_logs",
        ["transport_company_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_entity_id",
        "audit_logs",
        ["entity_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_entity_type",
        "audit_logs",
        ["entity_type"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_transport_company_id",
        "audit_logs",
        ["transport_company_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_university_created_at",
        "audit_logs",
        ["university_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_university_id",
        "audit_logs",
        ["university_id"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_user_created_at",
        "audit_logs",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop audit_logs table."""

    op.drop_index(
        "ix_audit_logs_user_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_user_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_university_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_university_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_transport_company_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_company_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_entity_id",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_entity_type",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_entity",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_action_created_at",
        table_name="audit_logs",
    )

    op.drop_index(
        "ix_audit_logs_action",
        table_name="audit_logs",
    )

    op.drop_table("audit_logs")
