import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.student import Student

QR_TOKEN_LENGTH = 32


def generate_qr_token() -> str:
    return secrets.token_urlsafe(QR_TOKEN_LENGTH)


def generate_unique_qr_token(db: Session) -> str:
    for _ in range(10):
        token = generate_qr_token()

        existing_student = (
            db.query(Student)
            .filter(Student.qr_token == token)
            .first()
        )

        if existing_student is None:
            return token

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="تولید توکن امن QR با مشکل مواجه شد",
    )


def ensure_student_qr_token(
    db: Session,
    student: Student,
) -> Student:

    if student.qr_token:
        return student

    student.qr_token = generate_unique_qr_token(db)

    db.commit()
    db.refresh(student)

    return student


def regenerate_student_qr_token(
    db: Session,
    student: Student,
) -> Student:

    student.qr_token = generate_unique_qr_token(db)

    db.commit()
    db.refresh(student)

    return student


def get_student_by_qr_token(
    db: Session,
    qr_token: str,
) -> Student:

    student = (
        db.query(Student)
        .filter(
            Student.qr_token == qr_token,
            Student.is_active.is_(True),
        )
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR کد دانشجو معتبر نیست",
        )

    return student