from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    CheckConstraint,
    Index,
)

from app.database import Base


class University(Base):
    __tablename__ = "universities"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_universities_name_not_empty",
        ),
        CheckConstraint(
            "length(trim(code)) > 0",
            name="ck_universities_code_not_empty",
        ),
        Index(
            "ix_universities_active",
            "is_active",
        ),
    )