from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class StationEvent(Base):
    __tablename__ = "station_events"

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

    station_id = Column(
        Integer,
        ForeignKey("stations.id"),
        nullable=False,
        index=True,
    )

    event_type = Column(
        String(20),
        nullable=False,
        index=True,
    )

    distance_meters = Column(
        Float,
        nullable=False,
    )

    speed_kmh = Column(
        Float,
        nullable=False,
    )

    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    trip = relationship("Trip")
    station = relationship("Station")

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_station_events_trip_id_positive",
        ),
        CheckConstraint(
            "station_id > 0",
            name="ck_station_events_station_id_positive",
        ),
        CheckConstraint(
            "length(trim(event_type)) > 0",
            name="ck_station_events_event_type_not_empty",
        ),
        CheckConstraint(
            "distance_meters >= 0",
            name="ck_station_events_distance_non_negative",
        ),
        CheckConstraint(
            "speed_kmh >= 0",
            name="ck_station_events_speed_non_negative",
        ),
        Index(
            "ix_station_events_trip_recorded_at",
            "trip_id",
            "recorded_at",
        ),
        Index(
            "ix_station_events_station_recorded_at",
            "station_id",
            "recorded_at",
        ),
        Index(
            "ix_station_events_trip_event_type",
            "trip_id",
            "event_type",
        ),
    )