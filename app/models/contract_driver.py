from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    Date,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class ContractDriver(Base):
    __tablename__ = "contract_drivers"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    contract_id = Column(
        Integer,
        ForeignKey("contracts.id"),
        nullable=False,
        index=True,
    )

    driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=False,
        index=True,
    )

    start_date = Column(
        Date,
        nullable=True,
    )

    end_date = Column(
        Date,
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    contract = relationship("Contract")
    driver = relationship("Driver")

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "driver_id",
            name="uq_contract_drivers_contract_driver",
        ),
        CheckConstraint(
            "contract_id > 0",
            name="ck_contract_drivers_contract_id_positive",
        ),
        CheckConstraint(
            "driver_id > 0",
            name="ck_contract_drivers_driver_id_positive",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_contract_drivers_date_range_valid",
        ),
        Index(
            "ix_contract_drivers_contract_active",
            "contract_id",
            "is_active",
        ),
        Index(
            "ix_contract_drivers_driver_active",
            "driver_id",
            "is_active",
        ),
    )