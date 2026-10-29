from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.trip import Trip
from app.models.student import Student
from app.models.trip_passenger import TripPassenger

from app.services.student_penalty_service import (
    validate_student_not_blocked,
)


RESERVATION_STATUSES = {
    "active",
    "waitlisted",
    "cancelled",
}

RESERVABLE_TRIP_STATUSES = {
    "scheduled",
}


def validate_positive_id(
    value: int,
    field_name: str,
) -> None:
    if value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} باید بزرگ‌تر از صفر باشد",
        )


def get_trip(
    db: Session,
    trip_id: int,
    *,
    for_update: bool = False,
) -> Trip:
    validate_positive_id(trip_id, "شناسه سفر")

    query = (
        db.query(Trip)
        .filter(Trip.id == trip_id)
    )

    if for_update:
        query = query.with_for_update()

    trip = query.first()

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
    validate_positive_id(student_id, "شناسه دانشجو")

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

    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجوی انتخاب‌شده فعال نیست",
        )

    validate_student_not_blocked(student)

    return student


def validate_trip_for_reservation(
    trip: Trip,
) -> None:
    if not trip.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این سفر غیرفعال است",
        )

    if trip.status not in RESERVABLE_TRIP_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رزرو فقط برای سفرهای برنامه‌ریزی‌شده امکان‌پذیر است",
        )

    if trip.trip_date < datetime.now(timezone.utc).date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای سفر گذشته امکان رزرو وجود ندارد",
        )


def validate_student_for_trip(
    student: Student,
    trip: Trip,
) -> None:
    if student.university_id != trip.university_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="دانشجو و سفر متعلق به یک دانشگاه نیستند",
        )


def validate_student_gender_for_trip(
    student: Student,
    trip: Trip,
) -> None:
    service = trip.service

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="سرویس این سفر مشخص نشده است",
        )

    gender_restriction = (
        service.gender_restriction or "mixed"
    ).strip().lower()

    if gender_restriction == "mixed":
        return

    if gender_restriction not in {"male", "female"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="محدودیت جنسیتی سرویس نامعتبر است",
        )

    if student.gender != gender_restriction:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این سرویس برای جنسیت دانشجوی انتخاب‌شده مجاز نیست",
        )


def get_active_reservation(
    db: Session,
    trip_id: int,
    student_id: int,
) -> Reservation | None:
    return (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.student_id == student_id,
            Reservation.status.in_(["active", "waitlisted"]),
        )
        .order_by(Reservation.reservation_time.desc())
        .first()
    )


def get_onboard_passenger(
    db: Session,
    trip_id: int,
    student_id: int,
) -> TripPassenger | None:
    return (
        db.query(TripPassenger)
        .filter(
            TripPassenger.trip_id == trip_id,
            TripPassenger.student_id == student_id,
            TripPassenger.boarding_time.is_not(None),
            TripPassenger.alighting_time.is_(None),
        )
        .first()
    )


def count_active_seated_reservations(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(func.count(Reservation.id))
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.status == "active",
            Reservation.is_standing.is_(False),
        )
        .scalar()
        or 0
    )


def count_active_standing_reservations(
    db: Session,
    trip_id: int,
) -> int:
    return (
        db.query(func.count(Reservation.id))
        .filter(
            Reservation.trip_id == trip_id,
            Reservation.status == "active",
            Reservation.is_standing.is_(True),
        )
        .scalar()
        or 0
    )


def has_reservation_capacity(
    db: Session,
    trip: Trip,
    is_standing: bool,
) -> bool:
    if is_standing:
        if not trip.allow_standing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="رزرو ایستاده برای این سفر مجاز نیست",
            )

        if trip.standing_capacity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت ایستاده برای این سفر مشخص نشده است",
            )

        if trip.standing_capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ظرفیت ایستاده این سفر صفر است",
            )

        return (
            count_active_standing_reservations(
                db,
                trip.id,
            )
            < trip.standing_capacity
        )

    if trip.seated_capacity is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ظرفیت صندلی برای این سفر مشخص نشده است",
        )

    if trip.seated_capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ظرفیت صندلی این سفر صفر است",
        )

    return (
        count_active_seated_reservations(
            db,
            trip.id,
        )
        < trip.seated_capacity
    )


def promote_waitlisted_reservations(
    db: Session,
    trip: Trip,
) -> int:
    if trip.status != "scheduled":
        return 0

    promoted_count = 0

    waitlisted = (
        db.query(Reservation)
        .filter(
            Reservation.trip_id == trip.id,
            Reservation.status == "waitlisted",
        )
        .order_by(
            Reservation.reservation_time.asc(),
            Reservation.id.asc(),
        )
        .with_for_update()
        .all()
    )

    for reservation in waitlisted:
        if not has_reservation_capacity(
            db,
            trip,
            reservation.is_standing,
        ):
            continue

        reservation.status = "active"
        promoted_count += 1

    return promoted_count


def create_reservation(
    db: Session,
    *,
    trip_id: int,
    student_id: int,
    is_standing: bool,
) -> Reservation:
    trip = get_trip(
        db,
        trip_id,
        for_update=True,
    )

    validate_trip_for_reservation(trip)

    student = get_student(
        db,
        student_id,
    )

    validate_student_for_trip(
        student,
        trip,
    )

    validate_student_gender_for_trip(
        student,
        trip,
    )

    existing_reservation = get_active_reservation(
        db,
        trip.id,
        student.id,
    )

    if existing_reservation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دانشجو قبلاً برای این سفر رزرو فعال یا در انتظار دارد",
        )

    onboard_passenger = get_onboard_passenger(
        db,
        trip.id,
        student.id,
    )

    if onboard_passenger:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این دانشجو در حال حاضر در این سفر سوار است و نیازی به رزرو ندارد",
        )

    has_capacity = has_reservation_capacity(
        db,
        trip,
        is_standing,
    )

    reservation = Reservation(
        trip_id=trip.id,
        student_id=student.id,
        reservation_time=datetime.now(timezone.utc),
        status="active" if has_capacity else "waitlisted",
        is_standing=is_standing,
    )

    try:
        db.add(reservation)
        db.commit()
        db.refresh(reservation)

    except IntegrityError:
        db.rollback()

        existing_reservation = get_active_reservation(
            db,
            trip.id,
            student.id,
        )

        if existing_reservation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="این دانشجو قبلاً برای این سفر رزرو فعال یا در انتظار دارد",
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="امکان ثبت رزرو وجود ندارد",
        )

    except Exception:
        db.rollback()
        raise

    return reservation


def cancel_reservation(
    db: Session,
    *,
    reservation_id: int,
) -> Reservation:
    validate_positive_id(
        reservation_id,
        "شناسه رزرو",
    )

    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id)
        .first()
    )

    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="رزرو موردنظر پیدا نشد",
        )

    if reservation.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این رزرو قبلاً لغو شده است",
        )

    if reservation.status not in {
        "active",
        "waitlisted",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="وضعیت رزرو نامعتبر است",
        )

    trip = get_trip(
        db,
        reservation.trip_id,
        for_update=True,
    )

    if trip.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رزرو فقط تا قبل از شروع سرویس قابل لغو است",
        )

    reservation.status = "cancelled"

    try:
        promote_waitlisted_reservations(
            db,
            trip,
        )

        db.commit()
        db.refresh(reservation)

    except Exception:
        db.rollback()
        raise

    return reservation