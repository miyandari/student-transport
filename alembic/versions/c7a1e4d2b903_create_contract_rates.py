"""create contract_rates

Revision ID: c7a1e4d2b903
Revises: b51825dfc407
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a1e4d2b903"
down_revision: Union[str, Sequence[str], None] = "b51825dfc407"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_type", sa.String(50), nullable=False),
        sa.Column("price_per_trip", sa.Integer(), nullable=False),
        sa.UniqueConstraint("contract_id", "vehicle_type", name="uq_contract_rates_contract_type"),
        sa.CheckConstraint("price_per_trip >= 0", name="ck_contract_rates_price_nonneg"),
        sa.CheckConstraint("length(trim(vehicle_type)) > 0", name="ck_contract_rates_type_not_blank"),
    )
    op.create_index("ix_contract_rates_id", "contract_rates", ["id"])
    op.create_index("ix_contract_rates_contract_id", "contract_rates", ["contract_id"])


def downgrade() -> None:
    op.drop_index("ix_contract_rates_contract_id", table_name="contract_rates")
    op.drop_index("ix_contract_rates_id", table_name="contract_rates")
    op.drop_table("contract_rates")
