from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
)

from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
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

    student_id = Column(
        Integer,
        ForeignKey("students.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    driver_id = Column(
        Integer,
        ForeignKey("drivers.id"),
        nullable=True,
        unique=True,
        index=True,
    )

    username = Column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    first_name = Column(
        String(100),
        nullable=True,
    )

    last_name = Column(
        String(100),
        nullable=True,
    )

    phone = Column(
        String(20),
        nullable=True,
    )

    role = Column(
        String(50),
        nullable=False,
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    university = relationship("University")
    transport_company = relationship("TransportCompany")
    student = relationship("Student")
    driver = relationship("Driver")

    __table_args__ = (
        CheckConstraint(
            "university_id IS NULL OR university_id > 0",
            name="ck_users_university_id_positive",
        ),
        CheckConstraint(
            "transport_company_id IS NULL OR transport_company_id > 0",
            name="ck_users_transport_company_id_positive",
        ),
        CheckConstraint(
            "student_id IS NULL OR student_id > 0",
            name="ck_users_student_id_positive",
        ),
        CheckConstraint(
            "driver_id IS NULL OR driver_id > 0",
            name="ck_users_driver_id_positive",
        ),
        CheckConstraint(
            "length(trim(username)) > 0",
            name="ck_users_username_not_empty",
        ),
        CheckConstraint(
            "length(trim(password_hash)) > 0",
            name="ck_users_password_hash_not_empty",
        ),
        CheckConstraint(
            "first_name IS NULL OR length(trim(first_name)) > 0",
            name="ck_users_first_name_not_empty",
        ),
        CheckConstraint(
            "last_name IS NULL OR length(trim(last_name)) > 0",
            name="ck_users_last_name_not_empty",
        ),
        CheckConstraint(
            "phone IS NULL OR length(trim(phone)) > 0",
            name="ck_users_phone_not_empty",
        ),
        CheckConstraint(
            "length(trim(role)) > 0",
            name="ck_users_role_not_empty",
        ),
        Index(
            "ix_users_university_active",
            "university_id",
            "is_active",
        ),
        Index(
            "ix_users_company_active",
            "transport_company_id",
            "is_active",
        ),
        Index(
            "ix_users_role_active",
            "role",
            "is_active",
        ),
    )