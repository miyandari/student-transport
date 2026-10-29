"""create notifications table

Revision ID: 4d9a2c8f1b7e
Revises: c1f48139cbb3
Create Date: 2026-10-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d9a2c8f1b7e"
down_revision: Union[str, Sequence[str], None] = "c1f48139cbb3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("university_id", sa.Integer(), nullable=True),
        sa.Column("transport_company_id", sa.Integer(), nullable=True),
        sa.Column("notification_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "user_id > 0",
            name="ck_notifications_user_id_positive",
        ),
        sa.CheckConstraint(
            "university_id IS NULL OR university_id > 0",
            name="ck_notifications_university_id_positive",
        ),
        sa.CheckConstraint(
            "transport_company_id IS NULL OR transport_company_id > 0",
            name="ck_notifications_company_id_positive",
        ),
        sa.CheckConstraint(
            "length(trim(notification_type)) > 0",
            name="ck_notifications_type_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_notifications_title_not_empty",
        ),
        sa.CheckConstraint(
            "length(trim(message)) > 0",
            name="ck_notifications_message_not_empty",
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
        "ix_notifications_id",
        "notifications",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_university_id",
        "notifications",
        ["university_id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_transport_company_id",
        "notifications",
        ["transport_company_id"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_notification_type",
        "notifications",
        ["notification_type"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_read_at",
        "notifications",
        ["read_at"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_user_read_created",
        "notifications",
        ["user_id", "is_read", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_university_created",
        "notifications",
        ["university_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_company_created",
        "notifications",
        ["transport_company_id", "created_at"],
        unique=False,
    )

    op.create_index(
        "ix_notifications_type_created",
        "notifications",
        ["notification_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_type_created",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_company_created",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_university_created",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_user_read_created",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_created_at",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_read_at",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_is_read",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_notification_type",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_transport_company_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_university_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_user_id",
        table_name="notifications",
    )
    op.drop_index(
        "ix_notifications_id",
        table_name="notifications",
    )

    op.drop_table("notifications")