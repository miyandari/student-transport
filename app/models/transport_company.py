from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    CheckConstraint,
    Index,
)

from app.database import Base


class TransportCompany(Base):
    __tablename__ = "transport_companies"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    registration_number = Column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    phone = Column(
        String(20),
        nullable=True,
    )

    address = Column(
        String(500),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_transport_companies_name_not_empty",
        ),
        CheckConstraint(
            "registration_number IS NULL "
            "OR length(trim(registration_number)) > 0",
            name="ck_transport_companies_registration_number_not_empty",
        ),
        CheckConstraint(
            "phone IS NULL OR length(trim(phone)) > 0",
            name="ck_transport_companies_phone_not_empty",
        ),
        CheckConstraint(
            "address IS NULL OR length(trim(address)) > 0",
            name="ck_transport_companies_address_not_empty",
        ),
        Index(
            "ix_transport_companies_active",
            "is_active",
        ),
    )