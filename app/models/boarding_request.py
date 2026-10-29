from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class BoardingRequest(Base):
    __tablename__ = "boarding_requests"

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

    boarding_station_id = Column(
        Integer,
        ForeignKey("stations.id"),
        nullable=True,
        index=True,
    )

    is_standing = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    requires_driver_approval = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="pending",
        index=True,
    )

    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    responded_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    responded_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    rejection_reason = Column(
        String(500),
        nullable=True,
    )

    trip = relationship(
        "Trip",
    )

    student = relationship(
        "Student",
    )

    boarding_station = relationship(
        "Station",
    )

    responded_by = relationship(
        "User",
    )

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_boarding_requests_trip_id_positive",
        ),

        CheckConstraint(
            "student_id > 0",
            name="ck_boarding_requests_student_id_positive",
        ),

        CheckConstraint(
            """
            boarding_station_id IS NULL
            OR boarding_station_id > 0
            """,
            name="ck_boarding_requests_station_id_positive",
        ),

        CheckConstraint(
            """
            status IN (
                'pending',
                'approved',
                'rejected',
                'cancelled'
            )
            """,
            name="ck_boarding_requests_status_valid",
        ),

        CheckConstraint(
            """
            rejection_reason IS NULL
            OR length(trim(rejection_reason)) > 0
            """,
            name="ck_boarding_requests_rejection_reason_valid",
        ),

        Index(
            "ix_boarding_requests_trip_status",
            "trip_id",
            "status",
        ),

        Index(
            "ix_boarding_requests_student_status",
            "student_id",
            "status",
        ),
    )