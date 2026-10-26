from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class TripAssignment(Base):
    __tablename__ = "trip_assignments"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    trip_id = Column(
        Integer,
        ForeignKey("trips.id"),
        nullable=False,
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

    assigned_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    replaces_assignment_id = Column(
        Integer,
        ForeignKey("trip_assignments.id"),
        nullable=True,
        index=True,
    )

    assignment_type = Column(
        String(30),
        nullable=False,
        default="primary",
        index=True,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    start_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    end_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    trip = relationship(
        "Trip",
        back_populates="assignments",
    )

    driver = relationship(
        "Driver",
    )

    vehicle = relationship(
        "Vehicle",
    )

    assigned_by_user = relationship(
        "User",
    )

    replaces_assignment = relationship(
        "TripAssignment",
        remote_side=[id],
        foreign_keys=[replaces_assignment_id],
    )

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_trip_assignments_trip_id_positive",
        ),
        CheckConstraint(
            "driver_id IS NULL OR driver_id > 0",
            name="ck_trip_assignments_driver_id_positive",
        ),
        CheckConstraint(
            "vehicle_id IS NULL OR vehicle_id > 0",
            name="ck_trip_assignments_vehicle_id_positive",
        ),
        CheckConstraint(
            "assigned_by_user_id > 0",
            name="ck_trip_assignments_assigned_by_user_id_positive",
        ),
        CheckConstraint(
            """
            replaces_assignment_id IS NULL
            OR replaces_assignment_id > 0
            """,
            name="ck_trip_assignments_replaces_id_positive",
        ),
        CheckConstraint(
            "length(trim(assignment_type)) > 0",
            name="ck_trip_assignments_type_not_empty",
        ),
        CheckConstraint(
            "reason IS NULL OR length(trim(reason)) > 0",
            name="ck_trip_assignments_reason_not_empty",
        ),
        CheckConstraint(
            "end_at IS NULL OR start_at IS NULL OR end_at >= start_at",
            name="ck_trip_assignments_date_range_valid",
        ),
        CheckConstraint(
            "driver_id IS NOT NULL OR vehicle_id IS NOT NULL",
            name="ck_trip_assignments_resource_required",
        ),
        Index(
            "ix_trip_assignments_trip_active",
            "trip_id",
            "is_active",
        ),
        Index(
            "ix_trip_assignments_driver_active",
            "driver_id",
            "is_active",
        ),
        Index(
            "ix_trip_assignments_vehicle_active",
            "vehicle_id",
            "is_active",
        ),
        Index(
            "ix_trip_assignments_trip_start",
            "trip_id",
            "start_at",
        ),
    )