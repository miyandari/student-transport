from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class Station(Base):
    __tablename__ = "stations"

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

    name = Column(
        String(200),
        nullable=False,
    )

    address = Column(
        String(500),
        nullable=True,
    )

    latitude = Column(
        Float,
        nullable=True,
    )

    longitude = Column(
        Float,
        nullable=True,
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

    route_stations = relationship(
        "RouteStation",
        back_populates="station",
        foreign_keys="RouteStation.station_id",
    )

    # =====================================================
    # Database Constraints / Indexes
    # =====================================================

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_stations_university_id_positive",
        ),

        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_stations_name_not_empty",
        ),

        CheckConstraint(
            "address IS NULL OR length(trim(address)) > 0",
            name="ck_stations_address_not_empty",
        ),

        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_stations_latitude_valid",
        ),

        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_stations_longitude_valid",
        ),

        CheckConstraint(
            """
            (latitude IS NULL AND longitude IS NULL)
            OR
            (latitude IS NOT NULL AND longitude IS NOT NULL)
            """,
            name="ck_stations_coordinates_pair",
        ),

        Index(
            "ix_stations_university_active",
            "university_id",
            "is_active",
        ),

        Index(
            "ix_stations_university_name",
            "university_id",
            "name",
        ),
    )