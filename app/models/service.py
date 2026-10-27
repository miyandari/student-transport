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


class Service(Base):
    __tablename__ = "services"

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

    route_id = Column(
        Integer,
        ForeignKey("routes.id"),
        nullable=False,
        index=True,
    )

    contract_id = Column(
        Integer,
        ForeignKey("contracts.id"),
        nullable=True,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    service_type = Column(
        String(50),
        nullable=False,
    )

    gender_restriction = Column(
        String(20),
        nullable=False,
        default="mixed",
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    university = relationship(
        "University",
    )

    route = relationship(
        "Route",
    )

    contract = relationship(
        "Contract",
    )

    schedules = relationship(
        "Schedule",
        back_populates="service",
        foreign_keys="Schedule.service_id",
    )

    trips = relationship(
        "Trip",
        back_populates="service",
        foreign_keys="Trip.service_id",
    )

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_services_university_id_positive",
        ),

        CheckConstraint(
            "route_id > 0",
            name="ck_services_route_id_positive",
        ),

        CheckConstraint(
            "contract_id IS NULL OR contract_id > 0",
            name="ck_services_contract_id_positive",
        ),

        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_services_name_not_empty",
        ),

        CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_services_code_not_empty",
        ),

        CheckConstraint(
            "length(trim(service_type)) > 0",
            name="ck_services_type_not_empty",
        ),

        CheckConstraint(
            "gender_restriction IN ('mixed', 'male', 'female')",
            name="ck_services_gender_restriction_valid",
        ),

        Index(
            "ix_services_university_active",
            "university_id",
            "is_active",
        ),

        Index(
            "ix_services_route_active",
            "route_id",
            "is_active",
        ),

        Index(
            "ix_services_contract_active",
            "contract_id",
            "is_active",
        ),

        Index(
            "ix_services_university_code",
            "university_id",
            "code",
        ),

        Index(
            "ix_services_university_gender_restriction",
            "university_id",
            "gender_restriction",
        ),
    )