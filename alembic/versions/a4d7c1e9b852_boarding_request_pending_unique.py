"""unique pending boarding request per (trip, student)

Revision ID: a4d7c1e9b852
Revises: e1f3a9c5b7d2
Create Date: 2026-11-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a4d7c1e9b852"
down_revision: Union[str, Sequence[str], None] = "e1f3a9c5b7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # قبل از ساخت ایندکس، درخواست‌های pending تکراری (به‌جز جدیدترین) لغو می‌شوند
    op.execute(
        """
        UPDATE boarding_requests SET status = 'cancelled'
        WHERE status = 'pending' AND id NOT IN (
            SELECT MAX(id) FROM boarding_requests
            WHERE status = 'pending' GROUP BY trip_id, student_id
        )
        """
    )
    op.create_index(
        "uq_boarding_requests_pending_trip_student",
        "boarding_requests",
        ["trip_id", "student_id"],
        unique=True,
        postgresql_where="status = 'pending'",
    )


def downgrade() -> None:
    op.drop_index("uq_boarding_requests_pending_trip_student", table_name="boarding_requests")
