from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    university_id = Column(
        Integer,
        ForeignKey("universities.id"),
        nullable=True,
        index=True,
    )

    transport_company_id = Column(
        Integer,
        ForeignKey("transport_companies.id"),
        nullable=True,
        index=True,
    )

    notification_type = Column(
        String(50),
        nullable=False,
        index=True,
    )

    title = Column(
        String(200),
        nullable=False,
    )

    message = Column(
        Text,
        nullable=False,
    )

    data = Column(
        JSON,
        nullable=True,
    )

    is_read = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    read_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "user_id > 0",
            name="ck_notifications_user_id_positive",
        ),
        CheckConstraint(
            "university_id IS NULL OR university_id > 0",
            name="ck_notifications_university_id_positive",
        ),
        CheckConstraint(
            "transport_company_id IS NULL "
            "OR transport_company_id > 0",
            name="ck_notifications_company_id_positive",
        ),
        CheckConstraint(
            "length(trim(notification_type)) > 0",
            name="ck_notifications_type_not_empty",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_notifications_title_not_empty",
        ),
        CheckConstraint(
            "length(trim(message)) > 0",
            name="ck_notifications_message_not_empty",
        ),
        Index(
            "ix_notifications_user_read_created",
            "user_id",
            "is_read",
            "created_at",
        ),
        Index(
            "ix_notifications_university_created",
            "university_id",
            "created_at",
        ),
        Index(
            "ix_notifications_company_created",
            "transport_company_id",
            "created_at",
        ),
        Index(
            "ix_notifications_type_created",
            "notification_type",
            "created_at",
        ),
    )