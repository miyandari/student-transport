"""add student gender, service gender restriction and active reservation index

Revision ID: 7f3c2a91d6e4
Revises: 5b746a74fefd
Create Date: 2026-10-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f3c2a91d6e4"
down_revision: Union[str, Sequence[str], None] = "5b746a74fefd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================
    # Students: gender
    # =====================================================

    op.add_column(
        "students",
        sa.Column(
            "gender",
            sa.String(length=20),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_students_gender",
        "students",
        ["gender"],
        unique=False,
    )

    op.create_index(
        "ix_students_university_gender",
        "students",
        ["university_id", "gender"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_students_gender_valid",
        "students",
        "gender IS NULL OR gender IN ('male', 'female')",
    )

    # =====================================================
    # Services: gender restriction
    # =====================================================

    op.add_column(
        "services",
        sa.Column(
            "gender_restriction",
            sa.String(length=20),
            nullable=True,
            server_default="mixed",
        ),
    )

    # Existing services are unrestricted.
    op.execute(
        """
        UPDATE services
        SET gender_restriction = 'mixed'
        WHERE gender_restriction IS NULL
        """
    )

    op.alter_column(
        "services",
        "gender_restriction",
        nullable=False,
        server_default=None,
    )

    op.create_index(
        "ix_services_gender_restriction",
        "services",
        ["gender_restriction"],
        unique=False,
    )

    op.create_index(
        "ix_services_university_gender_restriction",
        "services",
        ["university_id", "gender_restriction"],
        unique=False,
    )

    op.create_check_constraint(
        "ck_services_gender_restriction_valid",
        "services",
        "gender_restriction IN ('mixed', 'male', 'female')",
    )

    # =====================================================
    # Reservations: only one active reservation per
    # student for each trip
    # =====================================================

    op.create_index(
        "uq_reservations_active_trip_student",
        "reservations",
        ["trip_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    # =====================================================
    # Reservations
    # =====================================================

    op.drop_index(
        "uq_reservations_active_trip_student",
        table_name="reservations",
    )

    # =====================================================
    # Services
    # =====================================================

    op.drop_constraint(
        "ck_services_gender_restriction_valid",
        "services",
        type_="check",
    )

    op.drop_index(
        "ix_services_university_gender_restriction",
        table_name="services",
    )

    op.drop_index(
        "ix_services_gender_restriction",
        table_name="services",
    )

    op.drop_column(
        "services",
        "gender_restriction",
    )

    # =====================================================
    # Students
    # =====================================================

    op.drop_constraint(
        "ck_students_gender_valid",
        "students",
        type_="check",
    )

    op.drop_index(
        "ix_students_university_gender",
        table_name="students",
    )

    op.drop_index(
        "ix_students_gender",
        table_name="students",
    )

    op.drop_column(
        "students",
        "gender",
    )