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


class Feedback(Base):
    __tablename__ = "feedbacks"

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

    rating = Column(
        Integer,
        nullable=True,
    )

    feedback_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    title = Column(
        String(200),
        nullable=True,
    )

    message = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    is_resolved = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    trip = relationship("Trip")
    student = relationship("Student")

    __table_args__ = (
        CheckConstraint(
            "trip_id > 0",
            name="ck_feedbacks_trip_id_positive",
        ),
        CheckConstraint(
            "student_id > 0",
            name="ck_feedbacks_student_id_positive",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name="ck_feedbacks_rating_valid",
        ),
        CheckConstraint(
            "length(trim(feedback_type)) > 0",
            name="ck_feedbacks_type_not_empty",
        ),
        CheckConstraint(
            "title IS NULL OR length(trim(title)) > 0",
            name="ck_feedbacks_title_not_empty",
        ),
        CheckConstraint(
            "message IS NULL OR length(trim(message)) > 0",
            name="ck_feedbacks_message_not_empty",
        ),
        CheckConstraint(
            "title IS NOT NULL OR message IS NOT NULL",
            name="ck_feedbacks_content_required",
        ),
        Index(
            "ix_feedbacks_trip_created_at",
            "trip_id",
            "created_at",
        ),
        Index(
            "ix_feedbacks_student_created_at",
            "student_id",
            "created_at",
        ),
        Index(
            "ix_feedbacks_type_resolved",
            "feedback_type",
            "is_resolved",
        ),
    )