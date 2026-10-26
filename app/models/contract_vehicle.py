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


class ContractVehicle(Base):
    __tablename__ = "contract_vehicles"

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

    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
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
    vehicle = relationship("Vehicle")

    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "vehicle_id",
            name="uq_contract_vehicles_contract_vehicle",
        ),
        CheckConstraint(
            "contract_id > 0",
            name="ck_contract_vehicles_contract_id_positive",
        ),
        CheckConstraint(
            "vehicle_id > 0",
            name="ck_contract_vehicles_vehicle_id_positive",
        ),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_contract_vehicles_date_range_valid",
        ),
        Index(
            "ix_contract_vehicles_contract_active",
            "contract_id",
            "is_active",
        ),
        Index(
            "ix_contract_vehicles_vehicle_active",
            "vehicle_id",
            "is_active",
        ),
    )