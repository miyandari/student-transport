
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Time,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Schedule(Base):
    __tablename__ = "schedules"

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

    service_id = Column(
        Integer,
        ForeignKey("services.id"),
        nullable=False,
        index=True,
    )

    day_of_week = Column(
        Integer,
        nullable=False,
    )

    departure_time = Column(
        Time,
        nullable=False,
    )

    arrival_time = Column(
        Time,
        nullable=True,
    )

    schedule_type = Column(
        String(50),
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

    service = relationship(
        "Service",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_schedules_university_id_positive",
        ),

        CheckConstraint(
            "service_id > 0",
            name="ck_schedules_service_id_positive",
        ),

        CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_schedules_day_of_week_valid",
        ),

        CheckConstraint(
            "arrival_time IS NULL OR arrival_time > departure_time",
            name="ck_schedules_arrival_after_departure",
        ),

        CheckConstraint(
            "length(trim(schedule_type)) > 0",
            name="ck_schedules_schedule_type_not_empty",
        ),

        Index(
            "ix_schedules_service_day",
            "service_id",
            "day_of_week",
        ),

        Index(
            "ix_schedules_university_day",
            "university_id",
            "day_of_week",
        ),

        Index(
            "ix_schedules_active_day",
            "is_active",
            "day_of_week",
        ),
    )
