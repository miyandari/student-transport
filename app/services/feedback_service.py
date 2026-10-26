from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.models.trip import Trip
from app.models.student import Student
from app.models.trip_passenger import TripPassenger


def get_trip(
    db: Session,
    trip_id: int,
) -> Trip:
    trip = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
        .first()
    )

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    return trip


def get_student(
    db: Session,
    student_id: int,
) -> Student:
    student = (
        db.query(Student)
        .filter(Student.id == student_id)
        .first()
    )

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو پیدا نشد",
        )

    return student


def get_feedback(
    db: Session,
    feedback_id: int,
) -> Feedback:
    feedback = (
        db.query(Feedback)
        .filter(Feedback.id == feedback_id)
        .first()
    )

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="بازخورد موردنظر پیدا نشد",
        )

    return feedback


def validate_trip_for_feedback(
    trip: Trip,
) -> None:
    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )

    if trip.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ثبت بازخورد فقط پس از پایان سفر امکان‌پذیر است",
        )


def validate_student_for_feedback(
    student: Student,
) -> None:
    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی انتخاب‌شده فعال نیست",
        )


def validate_student_trip_access(
    student: Student,
    trip: Trip,
) -> None:
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو و سفر متعلق به یک دانشگاه نیستند",
        )


def validate_student_trip_participation(
    db: Session,
    trip_id: int,
    student_id: int,
) -> None:
    passenger = (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip_id,
            TripPassenger.student_id == student_id,
            TripPassenger.boarding_time.is_not(None),
        )
        .first()
    )

    if not passenger:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دانشجو در این سفر حضور نداشته است",
        )


def validate_duplicate_feedback(
    db: Session,
    trip_id: int,
    student_id: int,
) -> None:
    existing_feedback = (
        db.query(Feedback)
        .filter(
            Feedback.trip_id == trip_id,
            Feedback.student_id == student_id,
        )
        .first()
    )

    if existing_feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای این سفر قبلاً بازخورد ثبت شده است",
        )


def create_feedback(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
    rating: int,
    feedback_type: str,
    title: str | None,
    message: str | None,
) -> Feedback:

    trip = get_trip(
        db,
        trip_id,
    )

    validate_trip_for_feedback(
        trip,
    )

    student = get_student(
        db,
        student_id,
    )

    validate_student_for_feedback(
        student,
    )

    validate_student_trip_access(
        student,
        trip,
    )

    validate_student_trip_participation(
        db,
        trip.id,
        student.id,
    )

    validate_duplicate_feedback(
        db,
        trip.id,
        student.id,
    )

    feedback = Feedback(
        trip_id=trip.id,
        student_id=student.id,
        rating=rating,
        feedback_type=feedback_type,
        title=title,
        message=message,
        created_at=datetime.now(timezone.utc),
        is_resolved=False,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return feedback


def get_feedbacks(
    db: Session,
    *,
    trip_id: int | None = None,
    student_id: int | None = None,
    feedback_type: str | None = None,
    is_resolved: bool | None = None,
) -> list[Feedback]:

    query = (
        db.query(Feedback)
        .join(
            Trip,
            Trip.id == Feedback.trip_id,
        )
    )

    if trip_id is not None:
        query = query.filter(
            Feedback.trip_id == trip_id
        )

    if student_id is not None:
        query = query.filter(
            Feedback.student_id == student_id
        )

    if feedback_type is not None:
        feedback_type = feedback_type.strip()

        if feedback_type:
            query = query.filter(
                Feedback.feedback_type == feedback_type
            )

    if is_resolved is not None:
        query = query.filter(
            Feedback.is_resolved == is_resolved
        )

    return (
        query
        .order_by(
            Feedback.created_at.desc()
        )
        .all()
    )


def resolve_feedback(
    db: Session,
    *,
    feedback_id: int,
) -> Feedback:

    feedback = get_feedback(
        db,
        feedback_id,
    )

    if feedback.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این بازخورد قبلاً رسیدگی شده است",
        )

    feedback.is_resolved = True

    db.commit()
    db.refresh(feedback)

    return feedback