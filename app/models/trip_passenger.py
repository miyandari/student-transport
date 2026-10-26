from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class TripPassenger(Base):
    __tablename__ = "trip_passengers"

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

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=False,
        index=True,
    )

    boarding_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    boarding_station_id = Column(
        Integer,
        ForeignKey("stations.id"),
        nullable=True,
        index=True,
    )

    alighting_time = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    alighting_station_id = Column(
        Integer,
        ForeignKey("stations.id"),
        nullable=True,
        index=True,
    )

    boarding_method = Column(
        String(50),
        nullable=False,
    )

    is_standing = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    trip = relationship("Trip")
    student = relationship("Student")

    boarding_station = relationship(
        "Station",
        foreign_keys=[boarding_station_id],
    )

    alighting_station = relationship(
        "Station",
        foreign_keys=[alighting_station_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "trip_id",
            "student_id",
            name="uq_trip_passengers_trip_student",
        ),
        CheckConstraint(
            "trip_id > 0",
            name="ck_trip_passengers_trip_id_positive",
        ),
        CheckConstraint(
            "student_id > 0",
            name="ck_trip_passengers_student_id_positive",
        ),
        CheckConstraint(
            "boarding_station_id IS NULL OR boarding_station_id > 0",
            name="ck_trip_passengers_boarding_station_id_positive",
        ),
        CheckConstraint(
            "alighting_station_id IS NULL OR alighting_station_id > 0",
            name="ck_trip_passengers_alighting_station_id_positive",
        ),
        CheckConstraint(
            "length(trim(boarding_method)) > 0",
            name="ck_trip_passengers_boarding_method_not_empty",
        ),
        CheckConstraint(
            """
            alighting_time IS NULL
            OR boarding_time IS NULL
            OR alighting_time >= boarding_time
            """,
            name="ck_trip_passengers_time_order_valid",
        ),
        Index(
            "ix_trip_passengers_trip_student",
            "trip_id",
            "student_id",
        ),
        Index(
            "ix_trip_passengers_trip_boarding_station",
            "trip_id",
            "boarding_station_id",
        ),
        Index(
            "ix_trip_passengers_trip_alighting_station",
            "trip_id",
            "alighting_station_id",
        ),
    )