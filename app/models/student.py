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


class Student(Base):
    __tablename__ = "students"

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

    student_number = Column(
        String(50),
        nullable=False,
        index=True,
    )

    first_name = Column(
        String(100),
        nullable=False,
    )

    last_name = Column(
        String(100),
        nullable=False,
    )

    national_id = Column(
        String(20),
        nullable=True,
        index=True,
    )

    phone = Column(
        String(20),
        nullable=True,
    )

    qr_token = Column(
        String(64),
        nullable=True,
        unique=True,
        index=True,
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    university = relationship("University")

    __table_args__ = (
        CheckConstraint(
            "university_id > 0",
            name="ck_students_university_id_positive",
        ),
        CheckConstraint(
            "length(trim(student_number)) > 0",
            name="ck_students_student_number_not_empty",
        ),
        CheckConstraint(
            "length(trim(first_name)) > 0",
            name="ck_students_first_name_not_empty",
        ),
        CheckConstraint(
            "length(trim(last_name)) > 0",
            name="ck_students_last_name_not_empty",
        ),
        CheckConstraint(
            "national_id IS NULL OR length(trim(national_id)) > 0",
            name="ck_students_national_id_not_empty",
        ),
        CheckConstraint(
            "phone IS NULL OR length(trim(phone)) > 0",
            name="ck_students_phone_not_empty",
        ),
        CheckConstraint(
            "qr_token IS NULL OR length(trim(qr_token)) > 0",
            name="ck_students_qr_token_not_empty",
        ),
        Index(
            "ix_students_university_active",
            "university_id",
            "is_active",
        ),
        Index(
            "ix_students_university_student_number",
            "university_id",
            "student_number",
        ),
        Index(
            "ix_students_university_national_id",
            "university_id",
            "national_id",
        ),
    )