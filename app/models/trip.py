from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

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

    schedule_id = Column(
        Integer,
        ForeignKey("schedules.id"),
        nullable=True,
        index=True,
    )

    driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=True,
        index=True,
    )

    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=True,
        index=True,
    )

    seated_capacity = Column(
        Integer,
        nullable=True,
    )

    standing_capacity = Column(
        Integer,
        nullable=True,
    )

    allow_standing = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    trip_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    planned_departure_time = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    actual_departure_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    actual_arrival_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    status = Column(
        String(50),
        nullable=False,
        index=True,
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

    schedule = relationship(
        "Schedule",
    )

    driver = relationship(
        "Driver",
    )

    vehicle = relationship(
        "Vehicle",
    )

    assignments = relationship(
        "TripAssignment",
        back_populates="trip",
        foreign_keys="TripAssignment.trip_id",
        cascade="all, delete-orphan",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_trips_university_id_positive",
        ),

        CheckConstraint(
            "service_id > 0",
            name="ck_trips_service_id_positive",
        ),

        CheckConstraint(
            "schedule_id IS NULL OR schedule_id > 0",
            name="ck_trips_schedule_id_positive",
        ),

        CheckConstraint(
            "driver_id IS NULL OR driver_id > 0",
            name="ck_trips_driver_id_positive",
        ),

        CheckConstraint(
            "vehicle_id IS NULL OR vehicle_id > 0",
            name="ck_trips_vehicle_id_positive",
        ),

        CheckConstraint(
            "seated_capacity IS NULL OR seated_capacity > 0",
            name="ck_trips_seated_capacity_positive",
        ),

        CheckConstraint(
            "standing_capacity IS NULL OR standing_capacity >= 0",
            name="ck_trips_standing_capacity_non_negative",
        ),

        CheckConstraint(
            """
            allow_standing = TRUE
            OR standing_capacity IS NULL
            OR standing_capacity = 0
            """,
            name="ck_trips_standing_capacity_when_disabled",
        ),

        CheckConstraint(
            """
            allow_standing = FALSE
            OR (
                standing_capacity IS NOT NULL
                AND standing_capacity > 0
            )
            """,
            name="ck_trips_standing_capacity_when_enabled",
        ),

        CheckConstraint(
            "length(trim(status)) > 0",
            name="ck_trips_status_not_empty",
        ),

        CheckConstraint(
            """
            actual_departure_time IS NULL
            OR actual_departure_time >= planned_departure_time
            """,
            name="ck_trips_actual_departure_time_valid",
        ),

        CheckConstraint(
            """
            actual_arrival_time IS NULL
            OR actual_departure_time IS NULL
            OR actual_arrival_time >= actual_departure_time
            """,
            name="ck_trips_actual_arrival_time_valid",
        ),

        Index(
            "ix_trips_service_date",
            "service_id",
            "trip_date",
        ),

        Index(
            "ix_trips_driver_date",
            "driver_id",
            "trip_date",
        ),

        Index(
            "ix_trips_vehicle_date",
            "vehicle_id",
            "trip_date",
        ),

        Index(
            "ix_trips_schedule_date",
            "schedule_id",
            "trip_date",
        ),

        Index(
            "ix_trips_active_date_status",
            "is_active",
            "trip_date",
            "status",
        ),
    )