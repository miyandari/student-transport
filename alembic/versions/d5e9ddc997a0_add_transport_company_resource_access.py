"""add transport company resource access

Revision ID: d5e9ddc997a0
Revises: 1e77ee33b4b7
Create Date: 2026-10-25 20:39:05.605119

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e9ddc997a0"
down_revision: Union[str, Sequence[str], None] = "1e77ee33b4b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "contract_drivers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("driver_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"],
            ["drivers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_id",
            "driver_id",
            name="uq_contract_drivers_contract_driver",
        ),
    )

    op.create_index(
        op.f("ix_contract_drivers_contract_id"),
        "contract_drivers",
        ["contract_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_contract_drivers_driver_id"),
        "contract_drivers",
        ["driver_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_contract_drivers_id"),
        "contract_drivers",
        ["id"],
        unique=False,
    )

    op.create_table(
        "contract_vehicles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_id",
            "vehicle_id",
            name="uq_contract_vehicles_contract_vehicle",
        ),
    )

    op.create_index(
        op.f("ix_contract_vehicles_contract_id"),
        "contract_vehicles",
        ["contract_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_contract_vehicles_id"),
        "contract_vehicles",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_contract_vehicles_vehicle_id"),
        "contract_vehicles",
        ["vehicle_id"],
        unique=False,
    )

    op.add_column(
        "drivers",
        sa.Column(
            "transport_company_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_drivers_transport_company_id"),
        "drivers",
        ["transport_company_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_drivers_transport_company_id",
        "drivers",
        "transport_companies",
        ["transport_company_id"],
        ["id"],
    )

    op.add_column(
        "users",
        sa.Column(
            "transport_company_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_users_transport_company_id"),
        "users",
        ["transport_company_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_transport_company_id",
        "users",
        "transport_companies",
        ["transport_company_id"],
        ["id"],
    )

    op.add_column(
        "vehicles",
        sa.Column(
            "transport_company_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_vehicles_transport_company_id"),
        "vehicles",
        ["transport_company_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_vehicles_transport_company_id",
        "vehicles",
        "transport_companies",
        ["transport_company_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_vehicles_transport_company_id",
        "vehicles",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_vehicles_transport_company_id"),
        table_name="vehicles",
    )

    op.drop_column(
        "vehicles",
        "transport_company_id",
    )

    op.drop_constraint(
        "fk_users_transport_company_id",
        "users",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_users_transport_company_id"),
        table_name="users",
    )

    op.drop_column(
        "users",
        "transport_company_id",
    )

    op.drop_constraint(
        "fk_drivers_transport_company_id",
        "drivers",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_drivers_transport_company_id"),
        table_name="drivers",
    )

    op.drop_column(
        "drivers",
        "transport_company_id",
    )

    op.drop_index(
        op.f("ix_contract_vehicles_vehicle_id"),
        table_name="contract_vehicles",
    )

    op.drop_index(
        op.f("ix_contract_vehicles_id"),
        table_name="contract_vehicles",
    )

    op.drop_index(
        op.f("ix_contract_vehicles_contract_id"),
        table_name="contract_vehicles",
    )

    op.drop_table("contract_vehicles")

    op.drop_index(
        op.f("ix_contract_drivers_driver_id"),
        table_name="contract_drivers",
    )

    op.drop_index(
        op.f("ix_contract_drivers_id"),
        table_name="contract_drivers",
    )

    op.drop_index(
        op.f("ix_contract_drivers_contract_id"),
        table_name="contract_drivers",
    )

    op.drop_table("contract_drivers")