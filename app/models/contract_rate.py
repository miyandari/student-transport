from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ContractRate(Base):
    """نرخ هر سفر انجام‌شده به‌ازای نوع خودرو، طبق یک قرارداد (ریال)."""

    __tablename__ = "contract_rates"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_type = Column(String(50), nullable=False)
    price_per_trip = Column(Integer, nullable=False)

    contract = relationship("Contract")

    __table_args__ = (
        UniqueConstraint("contract_id", "vehicle_type", name="uq_contract_rates_contract_type"),
        CheckConstraint("price_per_trip >= 0", name="ck_contract_rates_price_nonneg"),
        CheckConstraint("length(trim(vehicle_type)) > 0", name="ck_contract_rates_type_not_blank"),
    )
