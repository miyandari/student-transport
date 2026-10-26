from sqlalchemy import (
    Column,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"

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

    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )

    latitude = Column(
        Float,
        nullable=False,
    )

    longitude = Column(
        Float,
        nullable=False,
    )

    speed = Column(
        Float,
        nullable=True,
    )

    heading = Column(
        Float,
        nullable=True,
    )

    recorded_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # =====================================================
    # Relationships
    # =====================================================

    trip = relationship(
        "Trip",
        foreign_keys=[trip_id],
    )

    vehicle = relationship(
        "Vehicle",
        foreign_keys=[vehicle_id],
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_vehicle_locations_trip_id_positive",
        ),

        CheckConstraint(
            "vehicle_id > 0",
            name="ck_vehicle_locations_vehicle_id_positive",
        ),

        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_vehicle_locations_latitude_valid",
        ),

        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_vehicle_locations_longitude_valid",
        ),

        CheckConstraint(
            "speed IS NULL OR speed >= 0",
            name="ck_vehicle_locations_speed_non_negative",
        ),

        CheckConstraint(
            "heading IS NULL OR (heading >= 0 AND heading < 360)",
            name="ck_vehicle_locations_heading_valid",
        ),

        Index(
            "ix_vehicle_locations_trip_recorded_at",
            "trip_id",
            "recorded_at",
        ),

        Index(
            "ix_vehicle_locations_vehicle_recorded_at",
            "vehicle_id",
            "recorded_at",
        ),
    )