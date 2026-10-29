"""add student no show fields

Revision ID: c1f48139cbb3
Revises: 7f3c2a91d6e4
Create Date: 2026-10-29 04:12:15.781083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1f48139cbb3"
down_revision: Union[str, Sequence[str], None] = "7f3c2a91d6e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "students",
        sa.Column("no_show_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "students",
        sa.Column("negative_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "students",
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        op.f("ix_students_no_show_count"),
        "students",
        ["no_show_count"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_negative_score"),
        "students",
        ["negative_score"],
        unique=False,
    )
    op.create_index(
        op.f("ix_students_blocked_until"),
        "students",
        ["blocked_until"],
        unique=False,
    )

    op.alter_column(
        "students",
        "no_show_count",
        server_default=None,
    )
    op.alter_column(
        "students",
        "negative_score",
        server_default=None,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_students_blocked_until"),
        table_name="students",
    )
    op.drop_index(
        op.f("ix_students_negative_score"),
        table_name="students",
    )
    op.drop_index(
        op.f("ix_students_no_show_count"),
        table_name="students",
    )

    op.drop_column("students", "blocked_until")
    op.drop_column("students", "negative_score")
    op.drop_column("students", "no_show_count")