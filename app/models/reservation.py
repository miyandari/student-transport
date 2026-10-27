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


class Reservation(Base):
    __tablename__ = "reservations"

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

    reservation_time = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    status = Column(
        String(50),
        nullable=False,
        index=True,
    )

    is_standing = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    trip = relationship("Trip")
    student = relationship("Student")

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_reservations_trip_id_positive",
        ),

        CheckConstraint(
            "student_id > 0",
            name="ck_reservations_student_id_positive",
        ),

        CheckConstraint(
            "length(trim(status)) > 0",
            name="ck_reservations_status_not_empty",
        ),

        Index(
            "ix_reservations_trip_status",
            "trip_id",
            "status",
        ),

        Index(
            "ix_reservations_student_status",
            "student_id",
            "status",
        ),

        Index(
            "uq_reservations_active_trip_student",
            "trip_id",
            "student_id",
            unique=True,
            postgresql_where=(
                status == "active"
            ),
        ),
    )