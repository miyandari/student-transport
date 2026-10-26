from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    CheckConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
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

    action = Column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_type = Column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    old_values = Column(
        JSON,
        nullable=True,
    )

    new_values = Column(
        JSON,
        nullable=True,
    )

    ip_address = Column(
        String(45),
        nullable=True,
    )

    user_agent = Column(
        String(500),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "user_id IS NULL OR user_id > 0",
            name="ck_audit_logs_user_id_positive",
        ),
        CheckConstraint(
            "university_id IS NULL OR university_id > 0",
            name="ck_audit_logs_university_id_positive",
        ),
        CheckConstraint(
            "transport_company_id IS NULL "
            "OR transport_company_id > 0",
            name="ck_audit_logs_company_id_positive",
        ),
        CheckConstraint(
            "entity_id IS NULL OR entity_id > 0",
            name="ck_audit_logs_entity_id_positive",
        ),
        CheckConstraint(
            "length(trim(action)) > 0",
            name="ck_audit_logs_action_not_empty",
        ),
        CheckConstraint(
            "length(trim(entity_type)) > 0",
            name="ck_audit_logs_entity_type_not_empty",
        ),
        CheckConstraint(
            "description IS NULL OR length(trim(description)) > 0",
            name="ck_audit_logs_description_not_empty",
        ),
        CheckConstraint(
            "ip_address IS NULL OR length(trim(ip_address)) > 0",
            name="ck_audit_logs_ip_address_not_empty",
        ),
        CheckConstraint(
            "user_agent IS NULL OR length(trim(user_agent)) > 0",
            name="ck_audit_logs_user_agent_not_empty",
        ),
        Index(
            "ix_audit_logs_user_created_at",
            "user_id",
            "created_at",
        ),
        Index(
            "ix_audit_logs_university_created_at",
            "university_id",
            "created_at",
        ),
        Index(
            "ix_audit_logs_company_created_at",
            "transport_company_id",
            "created_at",
        ),
        Index(
            "ix_audit_logs_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_audit_logs_action_created_at",
            "action",
            "created_at",
        ),
    )