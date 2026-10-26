from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Contract(Base):
    __tablename__ = "contracts"

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
        nullable=False,
        index=True,
    )

    contract_number = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    start_date = Column(
        Date,
        nullable=False,
    )

    end_date = Column(
        Date,
        nullable=False,
    )

    contract_amount = Column(
        Integer,
        nullable=True,
    )

    description = Column(
        String(1000),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    university = relationship("University")
    transport_company = relationship("TransportCompany")

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_contracts_university_id_positive",
        ),
        CheckConstraint(
            "transport_company_id > 0",
            name="ck_contracts_transport_company_id_positive",
        ),
        CheckConstraint(
            "length(trim(contract_number)) > 0",
            name="ck_contracts_contract_number_not_empty",
        ),
        CheckConstraint(
            "end_date >= start_date",
            name="ck_contracts_date_range_valid",
        ),
        CheckConstraint(
            "contract_amount IS NULL OR contract_amount >= 0",
            name="ck_contracts_amount_non_negative",
        ),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_contracts_description_not_empty",
        ),
        Index(
            "ix_contracts_university_active",
            "university_id",
            "is_active",
        ),
        Index(
            "ix_contracts_company_active",
            "transport_company_id",
            "is_active",
        ),
        Index(
            "ix_contracts_dates",
            "start_date",
            "end_date",
        ),
    )