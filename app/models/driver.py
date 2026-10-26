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


class Driver(Base):
    __tablename__ = "drivers"

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

    first_name = Column(
        String(100),
        nullable=False,
    )

    last_name = Column(
        String(100),
        nullable=False,
    )

    national_id = Column(
        String(20),
        nullable=True,
        index=True,
    )

    phone = Column(
        String(20),
        nullable=False,
    )

    license_number = Column(
        String(50),
        nullable=True,
        unique=True,
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

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_drivers_university_id_positive",
        ),

        CheckConstraint(
            "transport_company_id IS NULL OR transport_company_id > 0",
            name="ck_drivers_transport_company_id_positive",
        ),

        CheckConstraint(
            "length(trim(first_name)) > 0",
            name="ck_drivers_first_name_not_empty",
        ),

        CheckConstraint(
            "length(trim(last_name)) > 0",
            name="ck_drivers_last_name_not_empty",
        ),

        CheckConstraint(
            "national_id IS NULL OR length(trim(national_id)) > 0",
            name="ck_drivers_national_id_not_empty",
        ),

        CheckConstraint(
            "length(trim(phone)) > 0",
            name="ck_drivers_phone_not_empty",
        ),

        CheckConstraint(
            "license_number IS NULL OR length(trim(license_number)) > 0",
            name="ck_drivers_license_number_not_empty",
        ),

        Index(
            "ix_drivers_university_active",
            "university_id",
            "is_active",
        ),

        Index(
            "ix_drivers_company_active",
            "transport_company_id",
            "is_active",
        ),

        Index(
            "ix_drivers_national_id",
            "national_id",
        ),
    )
