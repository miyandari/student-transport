from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    university_id = Column(
        Integer,
        ForeignKey("universities.id"),
        nullable=False,
        index=True,
    )

    transport_company_id = Column(
        Integer,
        ForeignKey("transport_companies.id"),
        nullable=True,
        index=True,
    )

    driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=True,
        index=True,
    )

    plate_number = Column(
        String(20),
        nullable=False,
        unique=True,
        index=True,
    )

    vehicle_type = Column(
        String(50),
        nullable=False,
    )

    capacity = Column(
        Integer,
        nullable=False,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # Relationships
    # =====================================================

    university = relationship(
        "University",
    )

    transport_company = relationship(
        "TransportCompany",
    )

    driver = relationship(
        "Driver",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_vehicles_university_id_positive",
        ),

        CheckConstraint(
            "transport_company_id IS NULL OR transport_company_id > 0",
            name="ck_vehicles_transport_company_id_positive",
        ),

        CheckConstraint(
            "driver_id IS NULL OR driver_id > 0",
            name="ck_vehicles_driver_id_positive",
        ),

        CheckConstraint(
            "length(trim(plate_number)) > 0",
            name="ck_vehicles_plate_number_not_empty",
        ),

        CheckConstraint(
            "length(trim(vehicle_type)) > 0",
            name="ck_vehicles_type_not_empty",
        ),

        CheckConstraint(
            "capacity > 0",
            name="ck_vehicles_capacity_positive",
        ),

        Index(
            "ix_vehicles_university_active",
            "university_id",
            "is_active",
        ),

        Index(
            "ix_vehicles_company_active",
            "transport_company_id",
            "is_active",
        ),

        Index(
            "ix_vehicles_driver_active",
            "driver_id",
            "is_active",
        ),
    )
