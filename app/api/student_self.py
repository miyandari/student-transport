"""
endpointهای مخصوص اپ دانشجو.

این router باید در app/main.py «قبل از» students_router ثبت شود،
چون مسیرهای ثابت /students/me و /students/me/qr باید پیش از
مسیر پارامتری /students/{student_id} بررسی شوند. (در غیر این صورت
/students/me/qr با /students/{student_id}/qr تطبیق داده می‌شود و
خطای 422 می‌دهد.)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reservation import Reservation
from app.models.student import Student
from app.models.trip import Trip
from app.models.user import User

from app.core.dependencies import get_current_user
from app.core.roles import Roles, TRIP_VIEW_ROLES

from app.services.reservation_service import (
    count_active_seated_reservations,
    count_active_standing_reservations,
)
from app.services.student_qr_service import ensure_student_qr_token


router = APIRouter(
    tags=["Student App"],
)


# =========================================================
# Schemas
# =========================================================

class StudentSelfResponse(BaseModel):
    id: int
    university_id: int
    student_number: str
    first_name: str
    last_name: str
    gender: str
    is_active: bool
    no_show_count: int
    negative_score: int
    blocked_until: datetime | None
    is_blocked: bool


class TripAvailabilityResponse(BaseModel):
    trip_id: int
    seated_capacity: int | None
    seated_reserved: int
    seated_available: int | None
    allow_standing: bool
    standing_capacity: int | None
    standing_reserved: int
    standing_available: int | None
    waitlist_count: int


# =========================================================
# Helpers
# =========================================================

def _get_current_student(
    db: Session,
    current_user: User,
) -> Student:
    if current_user.role != Roles.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این بخش فقط برای دانشجویان است",
        )

    if current_user.student_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="حساب کاربری به دانشجو متصل نیست",
        )

    student = (
        db.query(Student)
        .filter(Student.id == current_user.student_id)
        .first()
    )

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="دانشجو پیدا نشد",
        )

    return student


def _is_blocked(student: Student) -> bool:
    blocked_until = student.blocked_until

    if blocked_until is None:
        return False

    if blocked_until.tzinfo is None:
        blocked_until = blocked_until.replace(tzinfo=timezone.utc)

    return blocked_until > datetime.now(timezone.utc)


# =========================================================
# GET /students/me
# =========================================================

@router.get(
    "/students/me",
    response_model=StudentSelfResponse,
)
def get_my_student(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = _get_current_student(db, current_user)

    return StudentSelfResponse(
        id=student.id,
        university_id=student.university_id,
        student_number=student.student_number,
        first_name=student.first_name,
        last_name=student.last_name,
        gender=student.gender,
        is_active=student.is_active,
        no_show_count=student.no_show_count or 0,
        negative_score=student.negative_score or 0,
        blocked_until=student.blocked_until,
        is_blocked=_is_blocked(student),
    )


# =========================================================
# GET /students/me/qr
# =========================================================

@router.get("/students/me/qr")
def get_my_student_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = _get_current_student(db, current_user)

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی غیرفعال نمی‌تواند QR فعال داشته باشد",
        )

    student = ensure_student_qr_token(db, student)

    return {
        "student_id": student.id,
        "qr_token": student.qr_token,
    }


# =========================================================
# GET /trips/{trip_id}/availability
# =========================================================

@router.get(
    "/trips/{trip_id}/availability",
    response_model=TripAvailabilityResponse,
)
def get_trip_availability(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in TRIP_VIEW_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما مجوز مشاهده ظرفیت سفر را ندارید",
        )

    trip = db.query(Trip).filter(Trip.id == trip_id).first()

    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="سفر موردنظر پیدا نشد",
        )

    # دانشجو و راننده فقط سفرهای دانشگاه خودشان را می‌بینند.
    if (
        current_user.role == Roles.STUDENT
        and current_user.university_id != trip.university_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="شما به این سفر دسترسی ندارید",
        )

    seated_reserved = count_active_seated_reservations(db, trip.id)
    standing_reserved = count_active_standing_reservations(db, trip.id)

    waitlist_count = (
        db.query(func.count(Reservation.id))
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status == "waitlisted",
        )
        .scalar()
        or 0
    )

    seated_available = (
        max(trip.seated_capacity - seated_reserved, 0)
        if trip.seated_capacity is not None
        else None
    )

    standing_available = (
        max(trip.standing_capacity - standing_reserved, 0)
        if trip.allow_standing and trip.standing_capacity is not None
        else None
    )

    return TripAvailabilityResponse(
        trip_id=trip.id,
        seated_capacity=trip.seated_capacity,
        seated_reserved=seated_reserved,
        seated_available=seated_available,
        allow_standing=trip.allow_standing,
        standing_capacity=trip.standing_capacity,
        standing_reserved=standing_reserved,
        standing_available=standing_available,
        waitlist_count=waitlist_count,
    )
