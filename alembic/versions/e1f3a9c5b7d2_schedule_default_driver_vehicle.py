"""schedule default driver/vehicle + assigned_by_user_id nullable

Revision ID: e1f3a9c5b7d2
Revises: c7a1e4d2b903
Create Date: 2026-11-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f3a9c5b7d2"
down_revision: Union[str, Sequence[str], None] = "c7a1e4d2b903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("default_driver_id", sa.Integer(), nullable=True))
    op.add_column("schedules", sa.Column("default_vehicle_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_schedules_default_driver_id"), "schedules", ["default_driver_id"])
    op.create_index(op.f("ix_schedules_default_vehicle_id"), "schedules", ["default_vehicle_id"])
    op.create_foreign_key("fk_schedules_default_driver_id", "schedules", "drivers", ["default_driver_id"], ["id"])
    op.create_foreign_key("fk_schedules_default_vehicle_id", "schedules", "vehicles", ["default_vehicle_id"], ["id"])
    # تخصیص خودکار توسط سیستم ثبت‌کننده ندارد
    op.alter_column("trip_assignments", "assigned_by_user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # توجه: اگر تخصیص خودکار (بدون ثبت‌کننده) وجود داشته باشد، بازگرداندن NOT NULL شکست می‌خورد
    op.alter_column("trip_assignments", "assigned_by_user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_constraint("fk_schedules_default_vehicle_id", "schedules", type_="foreignkey")
    op.drop_constraint("fk_schedules_default_driver_id", "schedules", type_="foreignkey")
    op.drop_index(op.f("ix_schedules_default_vehicle_id"), table_name="schedules")
    op.drop_index(op.f("ix_schedules_default_driver_id"), table_name="schedules")
    op.drop_column("schedules", "default_vehicle_id")
    op.drop_column("schedules", "default_driver_id")
