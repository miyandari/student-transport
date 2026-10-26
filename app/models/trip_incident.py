from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class TripIncident(Base):
    __tablename__ = "trip_incidents"

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

    reported_by_driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=True,
        index=True,
    )

    incident_type = Column(
        String(100),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_resolved = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    trip = relationship("Trip")
    reported_by_driver = relationship("Driver")

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_trip_incidents_trip_id_positive",
        ),
        CheckConstraint(
            "reported_by_driver_id IS NULL OR reported_by_driver_id > 0",
            name="ck_trip_incidents_driver_id_positive",
        ),
        CheckConstraint(
            "length(trim(incident_type)) > 0",
            name="ck_trip_incidents_type_not_empty",
        ),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_trip_incidents_description_not_empty",
        ),
        CheckConstraint(
            """
            resolved_at IS NULL
            OR resolved_at >= occurred_at
            """,
            name="ck_trip_incidents_resolution_time_valid",
        ),
        CheckConstraint(
            """
            (is_resolved = FALSE AND resolved_at IS NULL)
            OR
            (is_resolved = TRUE AND resolved_at IS NOT NULL)
            """,
            name="ck_trip_incidents_resolution_state_valid",
        ),
        Index(
            "ix_trip_incidents_trip_occurred_at",
            "trip_id",
            "occurred_at",
        ),
        Index(
            "ix_trip_incidents_trip_resolved",
            "trip_id",
            "is_resolved",
        ),
        Index(
            "ix_trip_incidents_driver_occurred_at",
            "reported_by_driver_id",
            "occurred_at",
        ),
    )